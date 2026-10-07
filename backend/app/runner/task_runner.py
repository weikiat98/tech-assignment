"""TaskRunner: runs analyses as background asyncio tasks (plan.md §3, single replica).

Interface kept small (start / resume / cancel) so an arq + Redis implementation can
replace it for horizontal scale-out without touching the API or the graph.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from langgraph.types import Command

from app.agents.graph import graph
from app.config import get_settings
from app.core.models import AgentEvent
from app.core.run_context import RunContext, current_run
from app.db.models import (
    AgentEventRow,
    Analysis,
    ChartRow,
    FactRow,
    LLMCallRow,
    QualityReportRow,
    ReportRow,
)
from app.db.session import SessionLocal
from app.export.markdown import render
from app.llm.router import llm_router
from app.observability import langfuse as lf

log = structlog.get_logger()


async def persist_event(event: AgentEvent) -> None:
    async with SessionLocal() as session:
        session.add(AgentEventRow(analysis_id=event.run_id, seq=event.seq, agent=event.agent, type=event.type,
                                  content=_jsonable(event.content), tokens=event.tokens, cost_usd=event.cost_usd,
                                  created_at=event.ts))
        await session.commit()


def _jsonable(obj: Any) -> Any:
    import json

    return json.loads(json.dumps(obj, default=str))


# Finished runs keep their in-memory context (DataFrames for the CSV export) up to this many; older ones are
# evicted together with their LangGraph checkpoint. Exports fall back to the stored result without it.
KEEP_FINISHED_RUNS = 25


class TaskRunner:
    def __init__(self) -> None:
        self.contexts: dict[str, RunContext] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.finished: list[str] = []

    def _mark_finished(self, run_id: str) -> None:
        if run_id in self.finished:
            self.finished.remove(run_id)
        self.finished.append(run_id)
        while len(self.finished) > KEEP_FINISHED_RUNS:
            old = self.finished.pop(0)
            self.contexts.pop(old, None)
            self.tasks.pop(old, None)
            try:
                graph.checkpointer.delete_thread(old)
            except Exception:  # noqa: BLE001 - eviction is best-effort
                log.warning("checkpoint_evict_failed", run_id=old)

    def start(self, run_id: str, query: str, options: dict[str, Any]) -> None:
        ctx = RunContext(run_id=run_id, query=query, options=dict(options), sink=persist_event)
        self.contexts[run_id] = ctx
        self.tasks[run_id] = asyncio.create_task(self._execute(ctx, {"query": query}))

    def resume(self, run_id: str, answer: str) -> bool:
        ctx = self.contexts.get(run_id)
        if ctx is None:
            return False
        self.tasks[run_id] = asyncio.create_task(self._execute(ctx, Command(resume=answer)))
        return True

    def cancel(self, run_id: str) -> bool:
        task = self.tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def _set_status(self, run_id: str, **fields: Any) -> None:
        async with SessionLocal() as session:
            analysis = await session.get(Analysis, run_id)
            if analysis is None:
                return
            for k, v in fields.items():
                setattr(analysis, k, v)
            await session.commit()

    async def _execute(self, ctx: RunContext, payload: Any) -> None:
        token = current_run.set(ctx)
        run_id = ctx.run_id
        config: dict[str, Any] = {"configurable": {"thread_id": run_id}, "recursion_limit": 80}
        try:
            await self._set_status(run_id, status="running", started_at=datetime.now(UTC))
            await ctx.emit("system", "status", {"state": "running"})
            tags = [f"llm_mode:{get_settings().llm_mode}", f"env:{get_settings().app_env}",
                    f"version:{get_settings().app_version}"]
            with lf.run_trace(run_id, ctx.query, tags) as callbacks:
                if callbacks:
                    config["callbacks"] = callbacks
                await graph.ainvoke(payload, config)
                snapshot = await graph.aget_state(config)
            if snapshot.next:
                interrupt_value = next((i.value for t in snapshot.tasks for i in t.interrupts), {})
                await ctx.emit("coordinator", "clarification", interrupt_value)
                await self._set_status(run_id, status="awaiting_input")
                return  # stays in memory until answered
            values = snapshot.values
            result = self.build_result(ctx, values)
            outcome = values.get("outcome", "completed")
            status = {"running": "completed", "out_of_scope": "completed"}.get(outcome, outcome)
            await self._persist_result(ctx, values, result, status)
            await ctx.emit("system", "final", {"status": status, "trace_url": lf.trace_url(run_id),
                                               "total_cost_usd": round(ctx.total_cost_usd, 5)})
            self._mark_finished(run_id)
        except asyncio.CancelledError:
            await self._set_status(run_id, status="cancelled", finished_at=datetime.now(UTC))
            await ctx.emit("system", "status", {"state": "cancelled"})
            self._mark_finished(run_id)
            raise
        except Exception as exc:  # noqa: BLE001 - a failed run must be recorded, not crash the server
            log.exception("analysis_failed", run_id=run_id)
            await ctx.emit("system", "error", {"message": f"{type(exc).__name__}: {exc}"})
            await self._set_status(run_id, status="failed", error=str(exc)[:2000], finished_at=datetime.now(UTC))
            self._mark_finished(run_id)
        finally:
            await self._flush_llm_calls(run_id)
            lf.flush()
            current_run.reset(token)

    @staticmethod
    def build_result(ctx: RunContext, values: dict[str, Any]) -> dict[str, Any]:
        result = {
            "query": ctx.query,
            "intent": values.get("intent"),
            "plan": values.get("plan"),
            "clarification": values.get("clarification"),
            "report": values.get("report"),
            "verification": values.get("verification"),
            "facts": [f.model_dump() for f in ctx.facts.values()],
            "charts": [c.model_dump() for c in ctx.charts.values()],
            "datasets": [r.summary() for r in ctx.datasets.values()],
            "context_notes": [n.model_dump() for n in ctx.context_notes],
            "warnings": ctx.warnings,
            "fallbacks": ctx.fallbacks,
            "llm_providers_used": sorted(ctx.llm_providers_used),
            "total_tokens": ctx.total_tokens,
            "total_cost_usd": round(ctx.total_cost_usd, 6),
            "trace_url": lf.trace_url(ctx.run_id),
            "outcome": values.get("outcome"),
            "extraction_summary": values.get("extraction_summary"),
            "analytics_summary": values.get("analytics_summary"),
        }
        result = _jsonable(result)
        result["markdown"] = render(result) if result.get("report") else None
        return result

    async def _persist_result(self, ctx: RunContext, values: dict, result: dict, status: str) -> None:
        async with SessionLocal() as session:
            analysis = await session.get(Analysis, ctx.run_id)
            if analysis is None:
                return
            analysis.status = status
            analysis.intent = result["intent"]
            analysis.plan = result["plan"]
            analysis.result = result
            analysis.total_tokens = ctx.total_tokens
            analysis.total_cost_usd = ctx.total_cost_usd
            analysis.finished_at = datetime.now(UTC)
            for f in ctx.facts.values():
                session.add(FactRow(analysis_id=ctx.run_id, fact_id=f.id, key=f.key, label=f.label, value=f.value,
                                    unit=f.unit, display=f.display, method=f.method, params=_jsonable(f.params),
                                    source_keys=f.source_keys))
            for c in ctx.charts.values():
                session.add(ChartRow(analysis_id=ctx.run_id, chart_id=c.id, title=c.title, spec=_jsonable(c.spec),
                                     fact_ids=c.fact_ids))
            for r in ctx.datasets.values():
                if r.quality:
                    session.add(QualityReportRow(analysis_id=ctx.run_id, dataset_key=r.key, score=r.quality.score,
                                                 issues=[i.model_dump() for i in r.quality.issues],
                                                 actions=r.quality.actions))
            if result.get("report"):
                session.add(ReportRow(analysis_id=ctx.run_id, markdown=result.get("markdown") or "",
                                      structured=result["report"], verification=result.get("verification")))
            await session.commit()

    async def _flush_llm_calls(self, run_id: str) -> None:
        calls = llm_router.drain_log(run_id)
        if not calls:
            return
        async with SessionLocal() as session:
            session.add_all(LLMCallRow(**c) for c in calls)
            await session.commit()


runner = TaskRunner()
