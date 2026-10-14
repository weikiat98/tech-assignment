from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalysisCreate(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    web_context: bool = False
    provider_preference: str | None = Field(None, description="auto | openai | gemini: tried first, the "
                                                              "others stay as fallback")


class AnalysisSummary(BaseModel):
    id: str
    query: str
    status: str
    created_at: datetime
    finished_at: datetime | None = None
    total_cost_usd: float = 0
    total_tokens: int = 0
    chat_id: str | None = None
    turn: int = 1
    version: int = 1


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


class MessageCreate(BaseModel):
    """A question in a chat: the first one (POST /chats) or a follow-up."""

    query: str = Field(min_length=3, max_length=1000)
    web_context: bool = False
    provider_preference: str | None = None


class ChatPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    pinned: bool | None = None


class ChatSummary(BaseModel):
    id: str
    title: str
    pinned: bool
    created_at: datetime
    updated_at: datetime
    status: str | None = None  # status of the newest run
    turns: int = 0


class ChatTurn(BaseModel):
    turn: int
    query: str
    versions: list[AnalysisSummary]  # oldest first; the last one is shown


class ChatDetail(ChatSummary):
    items: list[ChatTurn] = []
