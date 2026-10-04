"""Domain models shared by sources, tools, agents and the API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "status", "intent", "plan", "thought", "action", "observation", "handoff", "error", "fallback",
    "quality", "fact", "chart", "report_chunk", "clarification", "verification", "warning", "final",
]

TrustTier = Literal[1, 2, 3]

CANONICAL_COLUMNS = [
    "source_id", "dataset_id", "series", "series_code", "period", "period_start",
    "frequency", "value", "unit",
]


def utcnow() -> datetime:
    return datetime.now(UTC)


class AgentEvent(BaseModel):
    run_id: str
    seq: int = 0
    agent: str
    type: EventType
    content: dict[str, Any] = Field(default_factory=dict)
    tokens: int = 0
    cost_usd: float = 0.0
    ts: datetime = Field(default_factory=utcnow)


class QualityIssue(BaseModel):
    check: str
    severity: Literal["info", "warning", "error"]
    message: str


class QualityReport(BaseModel):
    dataset_key: str
    score: float
    row_count: int
    issues: list[QualityIssue] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class DatasetRecord(BaseModel):
    """A dataset fetched during a run, normalised to the canonical long format."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    key: str  # e.g. "singstat:M182841"
    source_id: str
    dataset_id: str
    title: str
    url: str | None = None
    unit: str | None = None
    frequency: str | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    is_fallback: bool = False
    fallback_reason: str | None = None
    trust_tier: TrustTier = 1
    notes: list[str] = Field(default_factory=list)
    footnote: str | None = None
    data_source_agency: str | None = None
    frame: Any = None  # pandas.DataFrame in canonical format (excluded from serialisation)
    quality: QualityReport | None = None

    def summary(self) -> dict[str, Any]:
        df: pd.DataFrame | None = self.frame
        series = sorted(df["series"].unique().tolist()) if df is not None and not df.empty else []
        periods = sorted(df["period"].unique().tolist()) if df is not None and not df.empty else []
        return {
            "key": self.key,
            "source_id": self.source_id,
            "dataset_id": self.dataset_id,
            "title": self.title,
            "url": self.url,
            "unit": self.unit,
            "frequency": self.frequency,
            "retrieved_at": self.retrieved_at.isoformat(),
            "is_fallback": self.is_fallback,
            "fallback_reason": self.fallback_reason,
            "trust_tier": self.trust_tier,
            "agency": self.data_source_agency,
            "footnote": self.footnote,
            "series": series,
            "period_range": [periods[0], periods[-1]] if periods else None,
            "row_count": 0 if df is None else int(len(df)),
            "quality": self.quality.model_dump() if self.quality else None,
            "notes": self.notes,
        }


class Fact(BaseModel):
    """A single computed number. The only place numbers in a report may come from."""

    id: str = ""  # assigned by the run context, e.g. "F12"
    key: str
    label: str
    value: float
    unit: str
    display: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    source_keys: list[str] = Field(default_factory=list)
    derived: bool = True


class Chart(BaseModel):
    id: str = ""
    title: str
    kind: str
    spec: dict[str, Any]
    fact_ids: list[str] = Field(default_factory=list)
    source_keys: list[str] = Field(default_factory=list)


class ContextNote(BaseModel):
    """Qualitative context from the web. Never used as a numeric Fact."""

    title: str
    url: str
    trust_tier: TrustTier
    excerpt: str
    injection_flagged: bool = False


# --- LLM structured outputs ---------------------------------------------------------


class ResearchIntent(BaseModel):
    topic: str = Field(description="Short restatement of what the user wants analysed")
    sectors: list[str] = Field(default_factory=list, description="Industry sectors of interest, SSIC-style names")
    metrics: list[str] = Field(
        default_factory=list,
        description="Metrics: employment, retrenchment, vacancies, compensation, gdp, unemployment, programmes",
    )
    start_year: int | None = None
    end_year: int | None = None
    analysis_types: list[str] = Field(
        default_factory=list, description="trend, comparison, correlation, forecast, share"
    )
    wants_web_context: bool = Field(False, description="True if qualitative context from the web would help")
    uses_internal_data: bool = Field(False, description="True if internal programme/grant data is relevant")
    needs_clarification: bool = False
    clarification_question: str | None = None
    clarification_suggestions: list[str] = Field(default_factory=list)
    confidence: float = Field(0.8, ge=0, le=1)
    out_of_scope: bool = False
    reasoning: str = Field("", description="One or two sentences explaining the interpretation")


class PlanTask(BaseModel):
    id: str
    agent: Literal["extraction", "analytics", "writer"]
    description: str
    source: Literal["singstat", "datagov", "mom", "internal", "web", "any"] = "any"
    query: str | None = Field(None, description="Search text for the source, if applicable")
    depends_on: list[str] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    reasoning: str = ""
    tasks: list[PlanTask]


class ReActStep(BaseModel):
    thought: str = Field(description="Short reasoning about what to do next")
    action: str = Field(description="Tool name to call, or 'finish'")
    action_input_json: str = Field("{}", description="JSON object with the tool arguments")
    final_answer: str | None = Field(None, description="Summary of results when action is 'finish'")


class Claim(BaseModel):
    text: str
    fact_ids: list[str] = Field(default_factory=list)
    source_keys: list[str] = Field(default_factory=list)


class ReportDraft(BaseModel):
    title: str
    executive_summary: str
    key_findings: list[Claim]
    sector_analysis: list[Claim] = Field(default_factory=list)
    policy_implications: list[Claim] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ClaimCheck(BaseModel):
    claim: str
    section: str
    passed: bool
    problems: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    passed: bool
    checks: list[ClaimCheck]
    numeric_pass_rate: float
    citation_pass_rate: float
    entity_pass_rate: float
    attempt: int
