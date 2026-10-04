from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalysisCreate(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    web_context: bool = False
    provider_preference: str | None = Field(None, description="openai | gemini | mock (informational)")


class AnalysisSummary(BaseModel):
    id: str
    query: str
    status: str
    created_at: datetime
    finished_at: datetime | None = None
    total_cost_usd: float = 0
    total_tokens: int = 0


class AnalysisDetail(AnalysisSummary):
    options: dict[str, Any] = {}
    intent: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class ClarifyRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=500)


class ChaosUpdate(BaseModel):
    fail_sources: list[str] | None = None
    fail_llm: list[str] | None = None
    inject_hallucination: bool | None = None
