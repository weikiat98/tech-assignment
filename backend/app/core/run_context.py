"""Per-run working state shared by agents and tools.

LangGraph state holds only small, serialisable values (intent, plan, ids). Heavy
objects (DataFrames, facts, charts) live here, keyed by run id, so checkpoints stay
small and a clarification interrupt can resume the same run.
"""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.events import event_bus
from app.core.models import AgentEvent, Chart, ContextNote, DatasetRecord, Fact

EventSink = Callable[[AgentEvent], Awaitable[None]]


@dataclass
class RunContext:
    run_id: str
    query: str
    options: dict[str, Any] = field(default_factory=dict)
    sink: EventSink | None = None  # persists events (set by the task runner)
    intent: Any = None  # ResearchIntent once interpreted
    plan: Any = None  # ResearchPlan once planned

    datasets: dict[str, DatasetRecord] = field(default_factory=dict)
    facts: dict[str, Fact] = field(default_factory=dict)
    charts: dict[str, Chart] = field(default_factory=dict)
    context_notes: list[ContextNote] = field(default_factory=list)
    web_pages: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    # Follow-ups (runner/followup.py): earlier turns of the chat and what was carried into this run.
    prior_turns: list[dict[str, Any]] = field(default_factory=list)
    carried_fact_ids: set[str] = field(default_factory=set)
    carried_dataset_keys: set[str] = field(default_factory=set)

    web_searches_used: int = 0
    web_fetches_used: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    llm_providers_used: set[str] = field(default_factory=set)
    fallbacks: list[str] = field(default_factory=list)
    known_titles: dict[str, str] = field(default_factory=dict)  # dataset id -> title seen in search results
    budget_exhausted: bool = False  # set by the LLM router once RUN_LLM_BUDGET_USD is spent
    _seq: int = 0

    async def emit(self, agent: str, type_: str, content: dict[str, Any] | None = None,
                   tokens: int = 0, cost_usd: float = 0.0) -> AgentEvent:
        self._seq += 1
        event = AgentEvent(run_id=self.run_id, seq=self._seq, agent=agent, type=type_,  # type: ignore[arg-type]
                           content=content or {}, tokens=tokens, cost_usd=cost_usd)
        event_bus.publish(event)
        if self.sink is not None:
            await self.sink(event)
        return event

    def add_fact(self, fact: Fact) -> Fact:
        # Same computation requested twice -> reuse the existing fact id.
        for existing in self.facts.values():
            if existing.key == fact.key:
                return existing
        fact.id = f"F{len(self.facts) + 1}"
        self.facts[fact.id] = fact
        return fact

    def add_chart(self, chart: Chart) -> Chart:
        chart.id = f"C{len(self.charts) + 1}"
        self.charts[chart.id] = chart
        return chart

    def add_dataset(self, record: DatasetRecord) -> DatasetRecord:
        self.datasets[record.key] = record
        return record

    def add_cost(self, tokens: int, cost_usd: float, provider: str) -> None:
        self.total_tokens += tokens
        self.total_cost_usd += cost_usd
        self.llm_providers_used.add(provider)


current_run: contextvars.ContextVar[RunContext] = contextvars.ContextVar("current_run")


def get_run() -> RunContext:
    return current_run.get()
