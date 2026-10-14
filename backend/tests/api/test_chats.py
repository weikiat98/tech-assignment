"""Chats: create, follow-up with carried context, retry versions, pin/rename/search/delete, legacy backfill."""

import asyncio

import httpx
import pytest
from sqlalchemy import select, text

from app.agents.suggestions import follow_ups
from app.db.init import backfill_chats
from app.db.models import Analysis, Chat
from app.db.session import SessionLocal
from app.main import app, lifespan

MAIN = "Analyse employment trends in the technology sector from 2020-2024"


@pytest.fixture(scope="module")
async def client():
    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def wait_done(client, analysis_id, max_seconds=60):
    for _ in range(max_seconds * 10):
        body = (await client.get(f"/api/v1/analyses/{analysis_id}")).json()
        if body["status"] not in ("queued", "running"):
            return body
        await asyncio.sleep(0.1)
    raise AssertionError("analysis did not finish")


def newest(chat: dict, turn: int) -> dict:
    return next(i for i in chat["items"] if i["turn"] == turn)["versions"][-1]


@pytest.fixture(scope="module")
async def conversation(client):
    """One chat with a first question and a follow-up, finished."""
    chat = (await client.post("/api/v1/chats", json={"query": MAIN})).json()
    first = await wait_done(client, newest(chat, 1)["id"])
    chat = (await client.post(f"/api/v1/chats/{chat['id']}/messages", json={"query": "What about finance?"})).json()
    second = await wait_done(client, newest(chat, 2)["id"])
    return chat["id"], first, second


async def test_create_chat_titles_it_from_the_question(client):
    resp = await client.post("/api/v1/chats", json={"query": MAIN})
    assert resp.status_code == 202
    chat = resp.json()
    assert chat["title"] == MAIN and chat["turns"] == 1
    run = newest(chat, 1)
    assert run["chat_id"] == chat["id"] and run["turn"] == 1 and run["version"] == 1
    done = await wait_done(client, run["id"])
    assert done["status"] == "completed"
    assert done["result"]["suggestions"], "answers carry follow-up suggestions"


async def test_follow_up_inherits_context_and_reuses_data(client, conversation):
    chat_id, first, second = conversation
    assert second["status"] == "completed" and second["result"]["verification"]["passed"]
    intent = second["result"]["intent"]
    assert intent["sectors"] == ["Financial And Insurance Services"]
    assert intent["metrics"] == first["result"]["intent"]["metrics"]  # inherited, not asked again
    assert (intent["start_year"], intent["end_year"]) == (2020, 2024)
    # Earlier facts are carried (and flagged); the new sector's series are fetched and sit beside the old ones.
    assert second["result"]["carried_fact_ids"]
    assert len(second["result"]["facts"]) > len(second["result"]["carried_fact_ids"])
    assert any("Financial" in f["label"] for f in second["result"]["facts"] if f["id"] not in
               second["result"]["carried_fact_ids"])
    assert not any("Information" in c["text"] for c in second["result"]["report"]["key_findings"]),         "an answer about finance must not be built from the technology facts of the earlier turn"


async def test_follow_up_for_the_same_series_reuses_the_download(client):
    chat = (await client.post("/api/v1/chats", json={"query": MAIN})).json()
    await wait_done(client, newest(chat, 1)["id"])
    chat = (await client.post(f"/api/v1/chats/{chat['id']}/messages",
                              json={"query": "Forecast this for the next two years"})).json()
    run = await wait_done(client, newest(chat, 2)["id"])
    assert run["result"]["intent"]["sectors"] == ["Information And Communications"]
    events = (await client.get(f"/api/v1/analyses/{run['id']}/events")).json()
    fetched = [e["content"]["result"] for e in events
               if e["type"] == "observation" and e["content"].get("tool") == "fetch_singstat"]
    assert fetched and all(r.get("reused") for r in fetched), "no second download of the same series"
    assert any(f["method"] == "linear_projection" for f in run["result"]["facts"])


async def test_chat_detail_lists_turns_and_versions(client, conversation):
    chat = (await client.get(f"/api/v1/chats/{conversation[0]}")).json()
    assert [i["turn"] for i in chat["items"]] == [1, 2]
    assert chat["items"][1]["query"] == "What about finance?"


async def test_retry_adds_a_version_and_keeps_the_old_one(client, conversation):
    chat_id = conversation[0]
    resp = await client.post(f"/api/v1/chats/{chat_id}/turns/2/retry")
    assert resp.status_code == 202
    versions = next(i for i in resp.json()["items"] if i["turn"] == 2)["versions"]
    assert [v["version"] for v in versions] == [1, 2]
    retried = await wait_done(client, versions[-1]["id"])
    assert retried["status"] == "completed" and retried["query"] == "What about finance?"
    assert retried["result"]["intent"]["sectors"] == ["Financial And Insurance Services"]
    assert (await client.post(f"/api/v1/chats/{chat_id}/turns/9/retry")).status_code == 404


async def test_one_question_at_a_time(client):
    chat = (await client.post("/api/v1/chats", json={"query": MAIN})).json()
    busy = await client.post(f"/api/v1/chats/{chat['id']}/messages", json={"query": "What about finance?"})
    assert busy.status_code == 409
    await wait_done(client, newest(chat, 1)["id"])


async def test_pin_rename_search_and_delete(client):
    chat = (await client.post("/api/v1/chats", json={"query": "Compare employment growth across sectors"})).json()
    await wait_done(client, newest(chat, 1)["id"])
    cid = chat["id"]
    patched = (await client.patch(f"/api/v1/chats/{cid}", json={"title": "  Sector   comparison ",
                                                                "pinned": True})).json()
    assert patched["title"] == "Sector comparison" and patched["pinned"] is True

    listing = (await client.get("/api/v1/chats")).json()
    assert listing[0]["id"] == cid, "pinned chats come first"
    assert [c["id"] for c in (await client.get("/api/v1/chats", params={"q": "sector comparison"})).json()] == [cid]
    by_question = (await client.get("/api/v1/chats", params={"q": "growth across"})).json()
    assert cid in [c["id"] for c in by_question], "search also matches the questions in a chat"
    assert (await client.patch(f"/api/v1/chats/{cid}", json={"title": ""})).status_code == 422

    assert (await client.delete(f"/api/v1/chats/{cid}")).status_code == 204
    assert (await client.get(f"/api/v1/chats/{cid}")).status_code == 404
    assert (await client.get(f"/api/v1/analyses/{newest(chat, 1)['id']}")).status_code == 404


async def test_analysis_endpoint_creates_a_chat_and_deleting_its_last_run_drops_it(client):
    created = (await client.post("/api/v1/analyses", json={"query": MAIN})).json()
    assert created["chat_id"] and created["turn"] == 1
    await wait_done(client, created["id"])
    assert (await client.get(f"/api/v1/chats/{created['chat_id']}")).status_code == 200
    await client.delete(f"/api/v1/analyses/{created['id']}")
    assert (await client.get(f"/api/v1/chats/{created['chat_id']}")).status_code == 404


async def test_legacy_analyses_become_one_question_chats(client):
    async with SessionLocal() as session:
        await session.execute(text("INSERT INTO analyses (id, query, status, options, total_tokens, total_cost_usd,"
                                   " created_at, turn, version) VALUES ('legacy-1', 'An old question', 'completed',"
                                   " '{}', 0, 0, '2026-10-01 04:00:00', 1, 1)"))
        await session.commit()
    assert await backfill_chats() >= 1
    async with SessionLocal() as session:
        row = await session.get(Analysis, "legacy-1")
        chat = await session.get(Chat, row.chat_id)
        assert chat.title == "An old question" and (row.turn, row.version) == (1, 1)
        assert await backfill_chats() == 0, "backfill is idempotent"
        assert (await session.scalars(select(Chat).where(Chat.id == row.chat_id))).one().id == chat.id


async def test_provider_preference_puts_that_provider_first(monkeypatch):
    from app.core.run_context import RunContext
    from app.llm.router import LLMRouter

    ctx = RunContext(run_id="r", query="q", options={"provider_preference": "gemini"})
    assert LLMRouter._preferred(["openai", "gemini"], ctx) == ["gemini", "openai"]
    assert LLMRouter._preferred(["openai", "gemini"], RunContext(run_id="r", query="q")) == ["openai", "gemini"]
    google = RunContext(run_id="r", query="q", options={"provider_preference": "google"})
    assert LLMRouter._preferred(["openai", "gemini"], google) == ["gemini", "openai"]
    unavailable = RunContext(run_id="r", query="q", options={"provider_preference": "openai"})
    assert LLMRouter._preferred(["gemini"], unavailable) == ["gemini"], "an unconfigured choice falls back"


def test_follow_up_suggestions_depend_on_the_answered_intent():
    suggestions = follow_ups({"sectors": ["Information And Communications"], "metrics": ["employment"],
                              "analysis_types": ["trend"]})
    assert 1 <= len(suggestions) <= 3 and suggestions[0].startswith("What about")
    assert "Forecast this for the next two years" in suggestions
    assert follow_ups({"out_of_scope": True}) == [] and follow_ups(None) == []


async def test_run_summary_for_non_technical_readers(client):
    chat = (await client.post("/api/v1/chats", json={"query": MAIN})).json()
    run = await wait_done(client, newest(chat, 1)["id"])
    s = (await client.get(f"/api/v1/analyses/{run['id']}/summary")).json()
    assert s["status"] == "completed" and s["verified"] is True and s["seconds"] is not None
    assert s["steps"] > 0 and s["retries"]["rewrites"] == 0
    assert {x["state"] for x in s["sources"]} <= {"live", "saved_copy", "failed"}
    assert any(x["state"] == "saved_copy" for x in s["sources"]), "offline tests serve recordings"
    assert any("offline" in w for w in s["worth_knowing"]), "saved copies are called out"
    assert s["trace_url"] is None, "Langfuse is not configured in tests"
    assert s["checks"]["numeric_pass_rate"] == 1
    assert (await client.get("/api/v1/analyses/nope/summary")).status_code == 404
