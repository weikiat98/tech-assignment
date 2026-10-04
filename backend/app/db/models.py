"""Relational schema (plan.md §8). Generic JSON columns keep it portable across Postgres and SQLite."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    intent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(10, 5), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentEventRow(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(40))
    type: Mapped[str] = mapped_column(String(20))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FactRow(Base):
    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    fact_id: Mapped[str] = mapped_column(String(10))
    key: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(40))
    display: Mapped[str] = mapped_column(String(60))
    method: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    source_keys: Mapped[list] = mapped_column(JSON, default=list)


class ChartRow(Base):
    __tablename__ = "charts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    chart_id: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(Text)
    spec: Mapped[dict] = mapped_column(JSON)
    fact_ids: Mapped[list] = mapped_column(JSON, default=list)


class QualityReportRow(Base):
    __tablename__ = "quality_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    dataset_key: Mapped[str] = mapped_column(String(120))
    score: Mapped[float] = mapped_column(Float)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)


class ReportRow(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    markdown: Mapped[str] = mapped_column(Text)
    structured: Mapped[dict] = mapped_column(JSON)
    verification: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class LLMCallRow(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    agent: Mapped[str] = mapped_column(String(40))
    task: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(60))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    success: Mapped[bool] = mapped_column(default=True)
    fallback_from: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# --- mock internal systems (synthetic data, clearly labelled) --------------------------


class InternalProgrammeEnrolment(Base):
    """Synthetic 'internal system' table: workforce training programme outcomes by sector."""

    __tablename__ = "internal_programme_enrolments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    sector: Mapped[str] = mapped_column(String(80), index=True)
    programme: Mapped[str] = mapped_column(String(80))
    enrolled: Mapped[int] = mapped_column(Integer)
    completed: Mapped[int] = mapped_column(Integer)
    placed_in_jobs: Mapped[int] = mapped_column(Integer)


class InternalGrantDisbursement(Base):
    """Synthetic 'internal system' table: grant disbursements by sector (S$ million)."""

    __tablename__ = "internal_grant_disbursements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    sector: Mapped[str] = mapped_column(String(80), index=True)
    scheme: Mapped[str] = mapped_column(String(80))
    amount_sgd_m: Mapped[float] = mapped_column(Float)
    firms_supported: Mapped[int] = mapped_column(Integer)
