"""Run details for non-technical readers (todo.md CL14): one aggregate of events, LLM calls and the result.

Langfuse shows every span and prompt, which suits engineers; this is the short version a researcher needs:
what happened, which sources were live, what was retried, and what is worth knowing before relying on it.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

LOW_QUALITY = 0.8


def build_summary(analysis: Any, events: list[Any], calls: list[Any], langfuse_on: bool) -> dict[str, Any]:
    result = analysis.result or {}
    verification = result.get("verification") or {}
    seconds = None
    if analysis.finished_at and analysis.created_at:
        seconds = round((analysis.finished_at - analysis.created_at).total_seconds(), 1)

    # Sources: live, a saved copy (snapshot), or failed (a fetch step that errored and was not recovered).
    sources = []
    for d in result.get("datasets", []):
        sources.append({"key": d["key"], "title": d["title"], "agency": d.get("agency"),
                        "state": "saved_copy" if d.get("is_fallback") else "live",
                        "reason": d.get("fallback_reason"), "quality": (d.get("quality") or {}).get("score")})
    failed = [e for e in events if e.type == "observation" and e.content.get("is_error")]
    for e in failed:
        tool = str(e.content.get("tool", ""))
        if tool.startswith(("fetch", "singstat", "datagov", "web_")):
            sources.append({"key": tool, "title": f"{tool.replace('_', ' ')} step", "agency": None, "state": "failed",
                            "reason": str((e.content.get("result") or {}).get("error", ""))[:200], "quality": None})

    providers = Counter(c.provider for c in calls if c.success)
    models = sorted({f"{c.provider}/{c.model}" for c in calls if c.success})
    llm_fallbacks = sorted({f"{c.fallback_from} -> {c.provider}" for c in calls if c.success and c.fallback_from})

    worth: list[str] = []
    worth += [f for f in result.get("fallbacks", [])]
    worth += [w for w in result.get("warnings", [])]
    removed = [e for e in events if e.type == "warning" and e.content.get("kind") == "claims_removed"]
    worth += [f"{e.content.get('count')} claim(s) were removed because they could not be verified" for e in removed]
    worth += [f"{s['title']} scored {s['quality']:.2f} for data quality" for s in sources
              if s["quality"] is not None and s["quality"] < LOW_QUALITY]
    worth += [f"{s['title']}: {s['reason']}" for s in sources if s["state"] == "saved_copy" and s["reason"]]

    carried = result.get("carried_fact_ids") or []
    return {
        "status": analysis.status,
        "outcome": result.get("outcome"),
        "verified": bool(verification.get("passed")) if verification else None,
        "seconds": seconds,
        "cost_usd": float(analysis.total_cost_usd or 0),
        "models": models,
        "model_calls": dict(providers),
        "llm_fallbacks": llm_fallbacks,
        "steps": sum(1 for e in events if e.type == "action"),
        "retries": {
            "rewrites": max(int(verification.get("attempt", 1)) - 1, 0) if verification else 0,
            "replans": sum(1 for e in events if e.type == "status" and e.content.get("state") == "replanning"),
            "failed_steps": len(failed),
        },
        "sources": sources,
        "checks": {k: verification.get(k) for k in ("numeric_pass_rate", "citation_pass_rate", "entity_pass_rate")},
        "facts_from_earlier_questions": len(carried),
        "worth_knowing": list(dict.fromkeys(worth)),
        # Only offered to engineers, and only when tracing is configured.
        "trace_url": result.get("trace_url") if langfuse_on else None,
    }
