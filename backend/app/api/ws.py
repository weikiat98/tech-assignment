"""WebSocket: live AgentEvents for one analysis, with replay of anything missed (?after=<seq>)."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.api.security import websocket_allowed
from app.core.events import event_bus
from app.db.models import AgentEventRow
from app.db.session import SessionLocal

router = APIRouter()
PING_SECONDS = 20


@router.websocket("/ws/analyses/{analysis_id}")
async def analysis_events(ws: WebSocket, analysis_id: str, after: int = 0) -> None:
    if not websocket_allowed(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    queue = event_bus.subscribe(analysis_id)  # subscribe before replay so nothing falls in the gap
    last_seq = after
    try:
        async with SessionLocal() as session:
            rows = (await session.scalars(select(AgentEventRow).where(AgentEventRow.analysis_id == analysis_id,
                                                                      AgentEventRow.seq > after)
                                          .order_by(AgentEventRow.seq))).all()
        for r in rows:
            await ws.send_json({"run_id": r.analysis_id, "seq": r.seq, "agent": r.agent, "type": r.type,
                                "content": r.content, "tokens": r.tokens, "cost_usd": float(r.cost_usd or 0),
                                "ts": r.created_at.isoformat()})
            last_seq = max(last_seq, r.seq)
        # Marks the end of the replay, so the UI can tell history from live events (it has no `seq`, so
        # clients that don't know it ignore it like a ping).
        await ws.send_json({"type": "replay_done", "last_seq": last_seq})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=PING_SECONDS)
            except TimeoutError:
                await ws.send_json({"type": "ping"})
                continue
            if event.seq <= last_seq:
                continue
            last_seq = event.seq
            await ws.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(analysis_id, queue)
        with contextlib.suppress(Exception):
            await ws.close()
