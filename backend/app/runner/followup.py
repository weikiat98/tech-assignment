"""Follow-up context (todo.md CL10): what a chat's earlier turns hand to the next question.

A follow-up run starts with the earlier answers' facts and (while the earlier runs are still in memory) their
datasets, so "what about finance?" can reuse the SingStat table already downloaded and the verifier accepts
earlier facts as citations. When an earlier run has been evicted, only its text and facts carry over.
"""

from __future__ import annotations

from typing import Any

from app.core.models import Fact
from app.core.run_context import RunContext

MAX_PRIOR_TURNS = 4


def carry_context(ctx: RunContext, prior: list[dict[str, Any]], live: dict[str, RunContext]) -> None:
    """prior: oldest first, each {"id", "query", "result"} of a completed earlier turn."""
    for item in prior[-MAX_PRIOR_TURNS:]:
        result = item.get("result") or {}
        report = result.get("report") or {}
        facts = []
        for raw in result.get("facts", []):
            carried = ctx.add_fact(Fact.model_validate(raw))
            ctx.carried_fact_ids.add(carried.id)
            facts.append({"id": carried.id, "label": carried.label, "display": carried.display})
        earlier = live.get(item["id"])
        for key, record in (earlier.datasets.items() if earlier else []):
            if record.frame is not None and key not in ctx.datasets:
                ctx.datasets[key] = record
                ctx.carried_dataset_keys.add(key)
        ctx.prior_turns.append({
            "question": item["query"],
            "summary": report.get("executive_summary", ""),
            "intent": result.get("intent") or {},
            "facts": facts,
            "dataset_keys": [d["key"] for d in result.get("datasets", [])],
        })


def history_text(ctx: RunContext) -> str:
    """The earlier turns as plain text for the coordinator and writer prompts ('' for a first question)."""
    if not ctx.prior_turns:
        return ""
    lines = ["Earlier in this conversation (oldest first):"]
    for i, turn in enumerate(ctx.prior_turns, 1):
        lines.append(f"Q{i}: {turn['question']}")
        if turn["summary"]:
            lines.append(f"A{i} (verified summary): {turn['summary']}")
        if turn["dataset_keys"]:
            lines.append(f"Datasets already collected: {', '.join(turn['dataset_keys'])}")
    return "\n".join(lines)
