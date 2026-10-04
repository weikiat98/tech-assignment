"""LangGraph orchestration (plan.md §4.2).

interpret -(ambiguous)-> [interrupt: clarify] -> plan -> extraction -> quality_gate -(no data, <=2)-> plan
                                                              quality_gate -> analytics -> write <-> verify -> END
"""

from __future__ import annotations

from datetime import date
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents import mock_policies as mock
from app.agents.prompts import ANALYTICS_EXTRA, EXTRACTION_EXTRA, INTERPRET, PLAN, WRITE
from app.agents.react import run_react
from app.core.models import ReportDraft, ResearchIntent, ResearchPlan
from app.core.run_context import RunContext, get_run
from app.llm.router import llm_router
from app.observability import langfuse as lf
from app.tools.analytics_tools import ANALYTICS_TOOLS
from app.tools.extraction import EXTRACTION_TOOLS
from app.verification.checks import drop_failing, verify

MAX_REPLANS = 2
MAX_REWRITES = 2


class AnalysisState(TypedDict, total=False):
    query: str
    clarification: str | None
    intent: dict[str, Any]
    plan: dict[str, Any]
    replans: int
    replan_feedback: str | None
    extraction_summary: str
    analytics_summary: str
    write_attempts: int
    verifier_feedback: list[str]
    report: dict[str, Any]
    verification: dict[str, Any]
    outcome: str  # completed | partial | out_of_scope


def _callbacks(ctx: RunContext) -> list:
    # Langfuse callbacks are attached once at graph level (runner); LLM calls inherit them through
    # LangChain's context propagation, so nodes pass nothing explicitly.
    return []


# --- Coordinator ----------------------------------------------------------------------


async def _interpret_once(ctx: RunContext, query: str, allow_clarification: bool) -> ResearchIntent:
    end = date.today().year - 1
    messages = [("system", INTERPRET.format(default_start=end - 4, default_end=end)),
                ("user", query + ("" if allow_clarification else
                                  "\n(The user already clarified; do not ask again.)"))]
    intent, _ = await llm_router.structured(
        "interpret", "coordinator", messages, ResearchIntent, ctx=ctx, callbacks=_callbacks(ctx),
        mock_fn=lambda: mock.interpret(query, ctx.options, allow_clarification))
    if not allow_clarification:
        intent.needs_clarification = False
    return intent


async def interpret_node(state: AnalysisState) -> dict:
    ctx = get_run()
    await ctx.emit("coordinator", "status", {"state": "interpreting", "query": state["query"]})
    intent = await _interpret_once(ctx, state["query"], allow_clarification=True)
    clarification = None
    if intent.needs_clarification:
        # The runner emits the "clarification" event when it sees this interrupt (the node re-runs on
        # resume, so emitting here would duplicate it).
        answer = interrupt({"question": intent.clarification_question,
                            "suggestions": intent.clarification_suggestions, "reasoning": intent.reasoning})
        clarification = str(answer)
        await ctx.emit("coordinator", "status", {"state": "clarified", "answer": clarification})
        intent = await _interpret_once(ctx, f"{state['query']} -- clarification: {clarification}",
                                       allow_clarification=False)
    ctx.intent = intent
    await ctx.emit("coordinator", "intent", intent.model_dump())
    return {"intent": intent.model_dump(), "clarification": clarification,
            "outcome": "out_of_scope" if intent.out_of_scope else "running"}


async def plan_node(state: AnalysisState) -> dict:
    ctx = get_run()
    intent = ResearchIntent.model_validate(state["intent"])
    ctx.intent = intent
    feedback = state.get("replan_feedback")
    messages = [("system", PLAN.format(feedback=f"\nPrevious attempt problem: {feedback}" if feedback else "")),
                ("user", intent.model_dump_json())]
    plan, _ = await llm_router.structured("plan", "coordinator", messages, ResearchPlan, ctx=ctx,
                                          callbacks=_callbacks(ctx), mock_fn=lambda: mock.plan(intent, feedback))
    ctx.plan = plan
    await ctx.emit("coordinator", "plan", plan.model_dump())
    return {"plan": plan.model_dump()}


# --- Workers --------------------------------------------------------------------------


async def extraction_node(state: AnalysisState) -> dict:
    ctx = get_run()
    plan = ResearchPlan.model_validate(state["plan"])
    tasks = "\n".join(f"- {t.id} [{t.source}] {t.description}" + (f" (query: {t.query})" if t.query else "")
                      for t in plan.tasks if t.agent == "extraction")
    intent = ctx.intent
    goal = (f"Research question: {state['query']}\nSectors: {intent.sectors or 'all'}; metrics: {intent.metrics}; "
            f"years {intent.start_year}-{intent.end_year}.\nYour tasks:\n{tasks}")
    await ctx.emit("coordinator", "handoff", {"to": "extraction", "tasks": tasks})
    summary = await run_react("extraction", goal, EXTRACTION_TOOLS, ctx, mock.extraction, EXTRACTION_EXTRA,
                              max_steps=18, callbacks=_callbacks(ctx))
    return {"extraction_summary": summary}


async def quality_gate_node(state: AnalysisState) -> dict:
    ctx = get_run()
    usable = [r for r in ctx.datasets.values()
              if r.frame is not None and not r.frame.empty and r.quality and r.quality.score > 0]
    cross = _cross_source_check(ctx)
    for message in cross:
        await ctx.emit("coordinator", "quality", {"dataset": "cross-source", "message": message})
    await ctx.emit("coordinator", "status", {"state": "quality_gate", "usable_datasets": len(usable),
                                             "datasets": [r.key for r in usable]})
    replans = state.get("replans", 0)
    if not usable and replans < MAX_REPLANS:
        feedback = "no usable datasets were found; broaden the search terms or use alternative sources"
        await ctx.emit("coordinator", "status", {"state": "replanning", "reason": feedback})
        return {"replans": replans + 1, "replan_feedback": feedback}
    return {"replans": replans, "replan_feedback": None,
            "outcome": "running" if usable else "partial"}


def _cross_source_check(ctx: RunContext) -> list[str]:
    """Compare the same series name across datasets on overlapping periods (>5% divergence is flagged)."""
    messages = []
    frames = [(k, r.frame) for k, r in ctx.datasets.items() if r.frame is not None and not r.frame.empty]
    for i, (ka, fa) in enumerate(frames):
        for kb, fb in frames[i + 1:]:
            common = set(fa["series"]) & set(fb["series"])
            for series in list(common)[:10]:
                a = fa[fa["series"] == series].set_index("period")["value"]
                b = fb[fb["series"] == series].set_index("period")["value"]
                joined = a.to_frame("a").join(b.to_frame("b"), how="inner").dropna()
                if joined.empty:
                    continue
                gap = ((joined["a"] - joined["b"]).abs() / joined["a"].abs()).max()
                status = "agree" if gap <= 0.05 else "DIVERGE"
                messages.append(f"{series}: {ka} vs {kb} {status} (max gap {gap:.1%} over {len(joined)} periods)")
    return messages


async def analytics_node(state: AnalysisState) -> dict:
    ctx = get_run()
    plan = ResearchPlan.model_validate(state["plan"])
    task = next((t.description for t in plan.tasks if t.agent == "analytics"), "Analyse the data")
    goal = (f"Research question: {state['query']}\nFocus sectors: {ctx.intent.sectors or 'all'}; "
            f"window {ctx.intent.start_year}-{ctx.intent.end_year}.\nTask: {task}")
    await ctx.emit("coordinator", "handoff", {"to": "analytics", "task": task})
    summary = await run_react("analytics", goal, ANALYTICS_TOOLS, ctx, mock.analytics, ANALYTICS_EXTRA,
                              max_steps=24, callbacks=_callbacks(ctx))
    return {"analytics_summary": summary}


async def write_node(state: AnalysisState) -> dict:
    ctx = get_run()
    attempt = state.get("write_attempts", 0) + 1
    feedback = state.get("verifier_feedback") or []
    facts = "\n".join(f"{f.id} | {f.label} | display: {f.display} | sources: {', '.join(f.source_keys)}"
                      for f in ctx.facts.values())
    sources = "\n".join(f"{r.key} | {r.title} | {r.data_source_agency or r.source_id} | tier {r.trust_tier}"
                        for r in ctx.datasets.values())
    notes = "\n".join(f"- {n.title} ({n.url}, tier {n.trust_tier}): {n.excerpt[:300]}" for n in ctx.context_notes)
    caveats = "\n".join(f"- {w}" for w in [*ctx.warnings, *ctx.fallbacks,
                                           *[f"{r.title}: {r.fallback_reason}" for r in ctx.datasets.values()
                                             if r.is_fallback]])
    fb = ("\nThe verifier rejected these claims in the previous draft; fix or remove them:\n"
          + "\n".join(f"- {f}" for f in feedback)) if feedback else ""
    messages = [("system", WRITE.format(feedback=fb)),
                ("user", f"Question: {state['query']}\nIntent: {ctx.intent.model_dump_json()}\n\nFACTS:\n{facts}\n\n"
                         f"SOURCES:\n{sources}\n\nWEB CONTEXT NOTES (<untrusted_content>):\n{notes or 'none'}\n\n"
                         f"KNOWN CAVEATS:\n{caveats or 'none'}")]
    await ctx.emit("writer", "status", {"state": "writing", "attempt": attempt})
    draft, _ = await llm_router.structured("write", "writer", messages, ReportDraft, ctx=ctx,
                                           callbacks=_callbacks(ctx),
                                           mock_fn=lambda: mock.write(ctx, attempt, feedback))
    # Stream the report section by section to the UI.
    await ctx.emit("writer", "report_chunk", {"section": "title", "text": draft.title, "attempt": attempt})
    await ctx.emit("writer", "report_chunk", {"section": "executive_summary", "text": draft.executive_summary,
                                              "attempt": attempt})
    for claim in draft.key_findings:
        await ctx.emit("writer", "report_chunk", {"section": "key_findings", "text": claim.text,
                                                  "fact_ids": claim.fact_ids, "attempt": attempt})
    return {"report": draft.model_dump(), "write_attempts": attempt}


async def verify_node(state: AnalysisState) -> dict:
    ctx = get_run()
    draft = ReportDraft.model_validate(state["report"])
    result = verify(draft, ctx, state.get("write_attempts", 1))
    failing = [f"\"{c.claim[:160]}\": {'; '.join(c.problems)}" for c in result.checks if not c.passed]
    await ctx.emit("verifier", "verification", {**result.model_dump(), "failing": failing})
    lf.score(ctx.run_id, "verifier_numeric_pass_rate", result.numeric_pass_rate)
    lf.score(ctx.run_id, "verifier_citation_pass_rate", result.citation_pass_rate)
    lf.score(ctx.run_id, "verifier_entity_pass_rate", result.entity_pass_rate)
    if result.passed or state.get("write_attempts", 1) > MAX_REWRITES:
        if not result.passed:
            draft = drop_failing(draft, result)
            await ctx.emit("verifier", "warning", {"kind": "claims_removed", "count": len(failing)})
        lf.score(ctx.run_id, "verification_passed", 1.0 if result.passed else 0.0)
        lf.score(ctx.run_id, "rewrites_needed", float(state.get("write_attempts", 1) - 1))
        outcome = state.get("outcome", "running")
        return {"report": draft.model_dump(), "verification": result.model_dump(), "verifier_feedback": [],
                "outcome": "completed" if outcome == "running" else outcome}
    await ctx.emit("verifier", "status", {"state": "rewrite_requested", "failing": len(failing)})
    return {"verification": result.model_dump(), "verifier_feedback": failing}


# --- Routing --------------------------------------------------------------------------


def after_interpret(state: AnalysisState) -> str:
    return END if state.get("outcome") == "out_of_scope" else "plan"


def after_quality(state: AnalysisState) -> str:
    return "plan" if state.get("replan_feedback") else "analytics"


def after_verify(state: AnalysisState) -> str:
    return "write" if state.get("verifier_feedback") else END


def build_graph():
    g = StateGraph(AnalysisState)
    g.add_node("interpret", interpret_node)
    g.add_node("plan", plan_node)
    g.add_node("extraction", extraction_node)
    g.add_node("quality_gate", quality_gate_node)
    g.add_node("analytics", analytics_node)
    g.add_node("write", write_node)
    g.add_node("verify", verify_node)
    g.add_edge(START, "interpret")
    g.add_conditional_edges("interpret", after_interpret, ["plan", END])
    g.add_edge("plan", "extraction")
    g.add_edge("extraction", "quality_gate")
    g.add_conditional_edges("quality_gate", after_quality, ["plan", "analytics"])
    g.add_edge("analytics", "write")
    g.add_edge("write", "verify")
    g.add_conditional_edges("verify", after_verify, ["write", END])
    return g.compile(checkpointer=MemorySaver())


graph = build_graph()
