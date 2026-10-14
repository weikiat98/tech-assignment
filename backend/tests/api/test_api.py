"""API smoke tests through the ASGI app: health, create/poll/export, history, clarify errors, chaos."""

import asyncio

import httpx
import pytest

from app.config import get_settings
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


async def test_health_and_readiness(client):
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    ready = (await client.get("/readyz")).json()
    assert ready["checks"]["database"] == "ok" and ready["ready"]


async def test_public_config(client):
    body = (await client.get("/api/v1/public-config")).json()
    assert body["token_required"] is False and len(body["sample_queries"]) == 6


async def test_create_poll_and_export(client):
    resp = await client.post("/api/v1/analyses", json={"query": MAIN})
    assert resp.status_code == 202
    body = await wait_done(client, resp.json()["id"])
    assert body["status"] == "completed" and body["result"]["verification"]["passed"]

    aid = body["id"]
    # R10: timestamps carry an explicit UTC offset, even on SQLite, so browsers don't read them as local time.
    assert body["created_at"].endswith(("Z", "+00:00")) and body["finished_at"].endswith(("Z", "+00:00"))
    md = await client.get(f"/api/v1/analyses/{aid}/export", params={"format": "md"})
    assert md.status_code == 200 and md.text.startswith("# ")
    js = await client.get(f"/api/v1/analyses/{aid}/export", params={"format": "json"})
    assert js.json()["query"] == MAIN
    csv = await client.get(f"/api/v1/analyses/{aid}/export", params={"format": "csv"})
    assert csv.headers["content-type"] == "application/zip" and csv.content[:2] == b"PK"
    docx = await client.get(f"/api/v1/analyses/{aid}/export", params={"format": "docx"})
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    bad = await client.get(f"/api/v1/analyses/{aid}/export", params={"format": "xlsx"})
    assert bad.status_code == 400

    events = (await client.get(f"/api/v1/analyses/{aid}/events")).json()
    assert [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    later = (await client.get(f"/api/v1/analyses/{aid}/events", params={"after": events[-5]["seq"]})).json()
    assert len(later) == 4

    history = (await client.get("/api/v1/analyses", params={"q": "technology"})).json()
    assert any(h["id"] == aid for h in history)


async def test_validation_and_not_found(client):
    assert (await client.post("/api/v1/analyses", json={"query": "x"})).status_code == 422
    assert (await client.get("/api/v1/analyses/does-not-exist")).status_code == 404


async def test_clarify_rejected_when_not_waiting(client):
    resp = await client.post("/api/v1/analyses", json={"query": MAIN})
    body = await wait_done(client, resp.json()["id"])
    r = await client.post(f"/api/v1/analyses/{body['id']}/clarify", json={"answer": "tech"})
    assert r.status_code == 409


async def test_chaos_toggles_locally(client):
    r = await client.put("/api/v1/admin/chaos", json={"fail_sources": ["datagov"]})
    assert r.status_code == 200 and r.json()["fail_sources"] == ["datagov"]
    r = await client.put("/api/v1/admin/chaos", json={"fail_sources": []})
    assert r.json()["fail_sources"] == []


async def test_chaos_admin_refused_on_shared_deployment(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "aws")
    assert (await client.get("/api/v1/admin/chaos")).json()["enabled"] is False
    r = await client.put("/api/v1/admin/chaos", json={"inject_hallucination": True})
    assert r.status_code == 403


async def test_access_token_required_when_configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_access_token", "s3cret-token")
    assert (await client.get("/api/v1/analyses")).status_code == 401
    ok = await client.get("/api/v1/analyses", headers={"X-Access-Token": "s3cret-token"})
    assert ok.status_code == 200
    assert (await client.get("/healthz")).status_code == 200  # health stays public for load balancers


async def test_llm_providers_status(client):
    body = (await client.get("/api/v1/llm/providers")).json()
    assert body["chain"] == ["mock"]
    assert {p["provider"] for p in body["providers"]} >= {"openai", "gemini", "mock"}
