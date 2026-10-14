"""REST API for chats: a conversation of questions, each answered by an analysis run (todo.md CL9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.runs import new_chat, start_run
from app.api.schemas import AnalysisSummary, ChatDetail, ChatPatch, ChatSummary, ChatTurn, MessageCreate
from app.api.security import require_token
from app.config import get_settings
from app.db.models import AgentEventRow, Analysis, Chat
from app.db.session import get_session
from app.main_limiter import limiter
from app.runner.task_runner import runner

router = APIRouter(prefix="/api/v1/chats", tags=["chats"], dependencies=[Depends(require_token)])

ACTIVE = ("queued", "running", "awaiting_input")


def _options(body: MessageCreate) -> dict:
    return {"web_context": body.web_context, "provider_preference": body.provider_preference}


async def _chat(session: AsyncSession, chat_id: str) -> Chat:
    chat = await session.get(Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


async def _runs(session: AsyncSession, chat_id: str) -> list[Analysis]:
    return list((await session.scalars(select(Analysis).where(Analysis.chat_id == chat_id)
                                       .order_by(Analysis.turn, Analysis.version))).all())


def _summary(chat: Chat, runs: list[Analysis]) -> ChatSummary:
    return ChatSummary(id=chat.id, title=chat.title, pinned=chat.pinned, created_at=chat.created_at,
                       updated_at=chat.updated_at, status=runs[-1].status if runs else None,
                       turns=len({r.turn for r in runs}))


def _detail(chat: Chat, runs: list[Analysis]) -> ChatDetail:
    by_turn: dict[int, list[Analysis]] = {}
    for r in runs:
        by_turn.setdefault(r.turn, []).append(r)
    items = [ChatTurn(turn=t, query=v[0].query,
                      versions=[AnalysisSummary.model_validate(a, from_attributes=True) for a in v])
             for t, v in sorted(by_turn.items())]
    return ChatDetail(**_summary(chat, runs).model_dump(), items=items)


async def _busy(session: AsyncSession, chat_id: str) -> bool:
    """A run still in progress in this process (a run orphaned by a server restart doesn't block the chat)."""
    ids = (await session.scalars(select(Analysis.id).where(Analysis.chat_id == chat_id,
                                                           Analysis.status.in_(ACTIVE)))).all()
    return any(i in runner.contexts for i in ids)


@router.post("", status_code=202, response_model=ChatDetail)
@limiter.limit(get_settings().rate_limit)
async def create_chat(request: Request, body: MessageCreate, session: AsyncSession = Depends(get_session)):
    chat = new_chat(session, body.query)
    analysis = await start_run(session, chat, body.query, _options(body), turn=1, version=1)
    return _detail(chat, [analysis])


@router.get("", response_model=list[ChatSummary])
async def list_chats(q: str | None = None, limit: int = 100, offset: int = 0,
                     session: AsyncSession = Depends(get_session)):
    stmt = select(Chat).order_by(desc(Chat.pinned), desc(Chat.updated_at)).limit(min(limit, 200)).offset(offset)
    if q:
        like = f"%{q}%"
        in_questions = select(Analysis.chat_id).where(Analysis.query.ilike(like))
        stmt = stmt.where(or_(Chat.title.ilike(like), Chat.id.in_(in_questions)))
    chats = (await session.scalars(stmt)).all()
    out = []
    for c in chats:
        out.append(_summary(c, await _runs(session, c.id)))
    return out


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(chat_id: str, session: AsyncSession = Depends(get_session)):
    chat = await _chat(session, chat_id)
    return _detail(chat, await _runs(session, chat_id))


@router.patch("/{chat_id}", response_model=ChatSummary)
async def patch_chat(chat_id: str, body: ChatPatch, session: AsyncSession = Depends(get_session)):
    chat = await _chat(session, chat_id)
    if body.title is not None:
        chat.title = " ".join(body.title.split())
    if body.pinned is not None:
        chat.pinned = body.pinned
    await session.commit()
    return _summary(chat, await _runs(session, chat_id))


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, session: AsyncSession = Depends(get_session)):
    await _chat(session, chat_id)
    ids = list((await session.scalars(select(Analysis.id).where(Analysis.chat_id == chat_id))).all())
    for run_id in ids:
        runner.cancel(run_id)
    if ids:
        await session.execute(delete(AgentEventRow).where(AgentEventRow.analysis_id.in_(ids)))
        await session.execute(delete(Analysis).where(Analysis.chat_id == chat_id))
    await session.execute(delete(Chat).where(Chat.id == chat_id))
    await session.commit()
    return Response(status_code=204)


@router.post("/{chat_id}/messages", status_code=202, response_model=ChatDetail)
@limiter.limit(get_settings().rate_limit)
async def add_message(request: Request, chat_id: str, body: MessageCreate,
                      session: AsyncSession = Depends(get_session)):
    chat = await _chat(session, chat_id)
    if await _busy(session, chat_id):
        raise HTTPException(status_code=409, detail="The previous question is still being answered")
    turn = max((r.turn for r in await _runs(session, chat_id)), default=0) + 1
    await start_run(session, chat, body.query, _options(body), turn=turn, version=1)
    return _detail(chat, await _runs(session, chat_id))


@router.post("/{chat_id}/turns/{turn}/retry", status_code=202, response_model=ChatDetail)
@limiter.limit(get_settings().rate_limit)
async def retry_turn(request: Request, chat_id: str, turn: int, session: AsyncSession = Depends(get_session)):
    """Answer a turn again: same question, same context as before. The earlier version is kept."""
    chat = await _chat(session, chat_id)
    if await _busy(session, chat_id):
        raise HTTPException(status_code=409, detail="A question in this chat is still being answered")
    versions = [r for r in await _runs(session, chat_id) if r.turn == turn]
    if not versions:
        raise HTTPException(status_code=404, detail="Turn not found")
    latest = versions[-1]
    await start_run(session, chat, latest.query, dict(latest.options or {}), turn=turn, version=latest.version + 1)
    return _detail(chat, await _runs(session, chat_id))
