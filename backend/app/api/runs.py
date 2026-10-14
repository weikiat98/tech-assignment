"""Starting analysis runs inside chats; shared by /analyses and /chats."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Analysis, Chat
from app.runner.task_runner import runner

TITLE_LENGTH = 80


def title_from(query: str) -> str:
    """Default chat title: the first question, trimmed on a word boundary."""
    text = " ".join(query.split())
    if len(text) <= TITLE_LENGTH:
        return text
    return text[:TITLE_LENGTH].rsplit(" ", 1)[0].rstrip(",;:") + "..."


def new_chat(session: AsyncSession, query: str) -> Chat:
    now = datetime.now(UTC)
    chat = Chat(id=str(uuid.uuid4()), title=title_from(query), created_at=now, updated_at=now)
    session.add(chat)
    return chat


async def prior_turns(session: AsyncSession, chat_id: str, before_turn: int) -> list[dict]:
    """The newest finished version of each earlier turn, oldest first (what a follow-up can build on)."""
    rows = (await session.scalars(select(Analysis).where(Analysis.chat_id == chat_id, Analysis.turn < before_turn,
                                                         Analysis.result.is_not(None))
                                  .order_by(Analysis.turn, Analysis.version))).all()
    latest: dict[int, Analysis] = {}
    for row in rows:
        if row.status in ("completed", "partial"):
            latest[row.turn] = row
    return [{"id": r.id, "query": r.query, "result": r.result} for _, r in sorted(latest.items())]


async def start_run(session: AsyncSession, chat: Chat, query: str, options: dict, turn: int,
                    version: int) -> Analysis:
    """Create the analysis row for a turn/version and start it. The chat must already be in the session."""
    analysis = Analysis(id=str(uuid.uuid4()), query=query.strip(), status="queued", options=options,
                        chat_id=chat.id, turn=turn, version=version)
    session.add(analysis)
    chat.updated_at = datetime.now(UTC)
    prior = await prior_turns(session, chat.id, turn) if turn > 1 else None
    await session.commit()
    runner.start(analysis.id, analysis.query, analysis.options, prior)
    return analysis
