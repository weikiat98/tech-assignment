"""LLM providers behind one interface: OpenAI, Google Gemini and a scripted MockLLM."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from app.config import get_settings, is_configured

Tier = Literal["strong", "fast"]


@dataclass
class LLMResult:
    value: Any
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


class LangChainProvider:
    """Shared logic for providers built on LangChain chat models."""

    name = "base"

    def model_name(self, tier: Tier) -> str:
        raise NotImplementedError

    def build(self, model: str):
        raise NotImplementedError

    @property
    def available(self) -> bool:
        raise NotImplementedError

    async def structured(self, tier: Tier, messages: list[tuple[str, str]], schema: type[BaseModel],
                         callbacks: list | None = None, mock_fn: Callable | None = None) -> LLMResult:
        model = self.model_name(tier)
        chain = self.build(model).with_structured_output(schema, include_raw=True)
        started = time.perf_counter()
        # Only pass callbacks explicitly when given: an empty list would override the trace context that
        # LangChain propagates from the enclosing LangGraph node (keeping LLM spans nested in the run trace).
        out = await chain.ainvoke(messages, config={"callbacks": callbacks} if callbacks else None)
        latency = int((time.perf_counter() - started) * 1000)
        if out.get("parsing_error") or out.get("parsed") is None:
            raise ValueError(f"{self.name} returned unparseable structured output: {out.get('parsing_error')}")
        usage = getattr(out.get("raw"), "usage_metadata", None) or {}
        return LLMResult(out["parsed"], self.name, model, usage.get("input_tokens", 0),
                         usage.get("output_tokens", 0), latency)

    async def text(self, tier: Tier, messages: list[tuple[str, str]], callbacks: list | None = None,
                   mock_fn: Callable | None = None) -> LLMResult:
        model = self.model_name(tier)
        started = time.perf_counter()
        msg = await self.build(model).ainvoke(messages, config={"callbacks": callbacks} if callbacks else None)
        usage = getattr(msg, "usage_metadata", None) or {}
        return LLMResult(msg.content, self.name, model, usage.get("input_tokens", 0),
                         usage.get("output_tokens", 0), int((time.perf_counter() - started) * 1000))


class OpenAIProvider(LangChainProvider):
    name = "openai"

    @property
    def available(self) -> bool:
        return is_configured(get_settings().openai_api_key)

    def model_name(self, tier: Tier) -> str:
        s = get_settings()
        return s.openai_model_strong if tier == "strong" else s.openai_model_fast

    def build(self, model: str):
        from langchain_openai import ChatOpenAI

        s = get_settings()
        return ChatOpenAI(model=model, api_key=s.openai_api_key, temperature=0, timeout=s.llm_timeout_s,
                          max_retries=1)


class GeminiProvider(LangChainProvider):
    name = "gemini"

    @property
    def available(self) -> bool:
        return is_configured(get_settings().google_api_key)

    def model_name(self, tier: Tier) -> str:
        s = get_settings()
        return s.gemini_model_strong if tier == "strong" else s.gemini_model_fast

    def build(self, model: str):
        from langchain_google_genai import ChatGoogleGenerativeAI

        s = get_settings()
        return ChatGoogleGenerativeAI(model=model, google_api_key=s.google_api_key, temperature=0,
                                      timeout=s.llm_timeout_s, max_retries=1)


class MockProvider:
    """Deterministic, scripted responses. Each call site supplies ``mock_fn`` that builds the
    answer from the run's real data, so a keyless run still exercises every tool and check."""

    name = "mock"
    available = True

    async def structured(self, tier: Tier, messages, schema, callbacks=None, mock_fn=None) -> LLMResult:
        if mock_fn is None:
            raise ValueError("MockLLM needs a scripted response (mock_fn) for this call")
        value = mock_fn()
        if not isinstance(value, schema):
            value = schema.model_validate(value)
        return LLMResult(value, self.name, "mock")

    async def text(self, tier: Tier, messages, callbacks=None, mock_fn=None) -> LLMResult:
        return LLMResult(mock_fn() if mock_fn else "", self.name, "mock")


PROVIDERS: dict[str, Any] = {"openai": OpenAIProvider(), "gemini": GeminiProvider(), "mock": MockProvider()}
