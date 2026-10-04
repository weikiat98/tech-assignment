"""REST API for analyses: create, list, detail, events replay, clarify, cancel, rerun, export."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AnalysisCreate, AnalysisDetail, AnalysisSummary, ClarifyRequest
from app.api.security import require_token
from app.config import get_settings
from app.db.models import AgentEventRow, Analysis
from app.db.session import get_session
from app.export import files
from app.export.markdown import render
from app.main_limiter import limiter
from app.runner.task_runner import runner

router = APIRouter(prefix="/api/v1/analyses", tags=["analyses"], dependencies=[Depends(require_token)])


async def _get(session: AsyncSession, analysis_id: str) -> Analysis:
    analysis = await session.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.post("", status_code=202, response_model=AnalysisSummary)
@limiter.limit(get_settings().rate_limit)
async def create_analysis(request: Request, body: AnalysisCreate, session: AsyncSession = Depends(get_session)):
    analysis = Analysis(id=str(uuid.uuid4()), query=body.query.strip(), status="queued",
                        options={"web_context": body.web_context, "provider_preference": body.provider_preference})
    session.add(analysis)
    await session.commit()
    runner.start(analysis.id, analysis.query, analysis.options)
    return AnalysisSummary.model_validate(analysis, from_attributes=True)


@router.get("", response_model=list[AnalysisSummary])
async def list_analyses(q: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0,
                        session: AsyncSession = Depends(get_session)):
    stmt = select(Analysis).order_by(desc(Analysis.created_at)).limit(min(limit, 200)).offset(offset)
    if q:
        stmt = stmt.where(or_(Analysis.query.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(Analysis.status == status)
    rows = (await session.scalars(stmt)).all()
    return [AnalysisSummary.model_validate(r, from_attributes=True) for r in rows]


@router.get("/{analysis_id}", response_model=AnalysisDetail)
async def get_analysis(analysis_id: str, session: AsyncSession = Depends(get_session)):
    return AnalysisDetail.model_validate(await _get(session, analysis_id), from_attributes=True)


@router.get("/{analysis_id}/events")
async def get_events(analysis_id: str, after: int = 0, session: AsyncSession = Depends(get_session)):
    await _get(session, analysis_id)
    rows = (await session.scalars(select(AgentEventRow).where(AgentEventRow.analysis_id == analysis_id,
                                                              AgentEventRow.seq > after)
                                  .order_by(AgentEventRow.seq))).all()
    return [{"run_id": r.analysis_id, "seq": r.seq, "agent": r.agent, "type": r.type, "content": r.content,
             "tokens": r.tokens, "cost_usd": float(r.cost_usd or 0), "ts": r.created_at.isoformat()} for r in rows]


@router.post("/{analysis_id}/clarify", status_code=202)
async def clarify(analysis_id: str, body: ClarifyRequest, session: AsyncSession = Depends(get_session)):
    analysis = await _get(session, analysis_id)
    if analysis.status != "awaiting_input":
        raise HTTPException(status_code=409, detail=f"Analysis is '{analysis.status}', not awaiting input")
    if not runner.resume(analysis_id, body.answer):
        raise HTTPException(status_code=410, detail="Run context expired (server restarted); start a new analysis")
    return {"status": "resumed"}


@router.post("/{analysis_id}/cancel", status_code=202)
async def cancel(analysis_id: str, session: AsyncSession = Depends(get_session)):
    await _get(session, analysis_id)
    return {"cancelled": runner.cancel(analysis_id)}


@router.post("/{analysis_id}/rerun", status_code=202, response_model=AnalysisSummary)
@limiter.limit(get_settings().rate_limit)
async def rerun(request: Request, analysis_id: str, session: AsyncSession = Depends(get_session)):
    original = await _get(session, analysis_id)
    body = AnalysisCreate(query=original.query, web_context=bool((original.options or {}).get("web_context")))
    return await create_analysis(request, body, session)


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis(analysis_id: str, session: AsyncSession = Depends(get_session)):
    await _get(session, analysis_id)
    await session.execute(delete(AgentEventRow).where(AgentEventRow.analysis_id == analysis_id))
    await session.execute(delete(Analysis).where(Analysis.id == analysis_id))
    await session.commit()
    return Response(status_code=204)


@router.get("/{analysis_id}/export")
async def export(analysis_id: str, format: str = "md", session: AsyncSession = Depends(get_session)):
    analysis = await _get(session, analysis_id)
    result = analysis.result
    if not result:
        raise HTTPException(status_code=409, detail="Analysis has no results yet")
    name = f"analysis-{analysis_id[:8]}"
    if format == "md":
        return Response(result.get("markdown") or render(result), media_type="text/markdown",
                        headers={"Content-Disposition": f'attachment; filename="{name}.md"'})
    if format == "json":
        return Response(files.to_json(result), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{name}.json"'})
    if format == "csv":
        ctx = runner.contexts.get(analysis_id)
        frames = {k: r.frame for k, r in ctx.datasets.items()} if ctx else None
        return Response(files.to_csv_zip(result, frames), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{name}-data.zip"'})
    if format == "pdf":
        try:
            pdf = await files.to_pdf(result)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"PDF service unavailable: {exc}") from exc
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})
    if format == "html":
        return Response(files.to_html(result), media_type="text/html")
    raise HTTPException(status_code=400, detail="format must be one of md, json, csv, pdf, html")
