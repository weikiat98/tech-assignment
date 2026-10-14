"""WebSocket replay: every stored event, then a `replay_done` marker the UI uses to tell history from live events.

The handler is called directly with a fake socket on the test's own event loop. (Starlette's TestClient runs a
second loop in a thread, which shared the pooled aiosqlite connections with the other API tests and was flaky.)
"""

import asyncio

import httpx
import pytest
from fastapi import WebSocketDisconnect

from app.api.ws import analysis_events
from app.main import app, lifespan

MAIN = "Analyse employment trends in the technology sector from 2020-2024"


class FakeSocket:
    """Records what the handler sends and disconnects as soon as the replay marker arrives."""

    headers: dict = {}
    query_params: dict = {}

    def __init__(self):
        self.sent: list[dict] = []

    async def accept(self):
        pass

    async def close(self):
        pass

    async def send_json(self, msg: dict):
        self.sent.append(msg)
        if msg.get("type") == "replay_done":
            raise WebSocketDisconnect()

    async def send_text(self, text: str):
        raise AssertionError("no live events expected after a finished run")


@pytest.fixture(scope="module")
async def client():
    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def wait_done(client, analysis_id, max_seconds=60):
    for _ in range(max_seconds * 10):
        if (await client.get(f"/api/v1/analyses/{analysis_id}")).json()["status"] not in ("queued", "running"):
            return
        await asyncio.sleep(0.1)
    raise AssertionError("analysis did not finish")


async def _replay(aid: str, after: int = 0) -> tuple[list[dict], dict]:
    ws = FakeSocket()
    await analysis_events(ws, aid, after=after)
    *events, done = ws.sent
    return events, done


async def test_replay_ends_with_a_marker_after_the_last_stored_event(client):
    aid = (await client.post("/api/v1/analyses", json={"query": MAIN})).json()["id"]
    await wait_done(client, aid)
    stored = (await client.get(f"/api/v1/analyses/{aid}/events")).json()

    events, done = await _replay(aid)
    assert [e["seq"] for e in events] == [e["seq"] for e in stored]
    assert done == {"type": "replay_done", "last_seq": stored[-1]["seq"]}
    assert "seq" not in done  # older clients skip messages without a seq

    # Reconnecting after the last seq replays nothing and reports the same watermark.
    events, done = await _replay(aid, after=stored[-1]["seq"])
    assert events == [] and done["last_seq"] == stored[-1]["seq"]
