"""LLMRouter: per-task model tier, provider fallback chain, circuit breaker, cost tracking."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from app.core.chaos import chaos
from app.core.run_context import RunContext
from app.llm.costs import cost_usd
from app.llm.providers import PROVIDERS, LLMResult, Tier

TASK_TIERS: dict[str, Tier] = {
    "interpret": "strong",
    "plan": "strong",
    "react_step": "fast",
    "write": "strong",
    "extract": "fast",
    "judge": "fast",
}

FAILURE_THRESHOLD = 3
OPEN_SECONDS = 60


class AllProvidersFailed(RuntimeError):
    pass


@dataclass
class Breaker:
    failures: int = 0
    open_until: float = 0.0

    @property
    def is_open(self) -> bool:
        return time.monotonic() < self.open_until

    def record(self, ok: bool) -> None:
        if ok:
            self.failures, self.open_until = 0, 0.0
            return
        self.failures += 1
        if self.failures >= FAILURE_THRESHOLD:
            self.open_until = time.monotonic() + OPEN_SECONDS


@dataclass
class LLMRouter:
    breakers: dict[str, Breaker] = field(default_factory=dict)
    call_log: list[dict[str, Any]] = field(default_factory=list)  # flushed to llm_calls by the runner

    def chain(self) -> list[str]:
        settings = get_settings()
        if settings.llm_mode == "mock":
            return ["mock"]
        live = [p for p in settings.provider_order if p in PROVIDERS and PROVIDERS[p].available]
        if settings.llm_mode == "live":
            return live
        if not live:
            return ["mock"]
        return live + (["mock"] if settings.llm_mock_last_resort else [])

    def status(self) -> list[dict[str, Any]]:
        settings = get_settings()
        out = []
        for name in [*settings.provider_order, "mock"]:
            provider = PROVIDERS.get(name)
            if provider is None:
                continue
            breaker = self.breakers.get(name, Breaker())
            out.append({"provider": name, "configured": bool(provider.available),
                        "in_chain": name in self.chain(), "circuit_open": breaker.is_open,
                        "recent_failures": breaker.failures, "chaos_down": name in chaos.fail_llm})
        return out

    async def _run(self, kind: str, task: str, agent: str, messages: list[tuple[str, str]],
                   ctx: RunContext | None, schema: type[BaseModel] | None, mock_fn: Callable | None,
                   callbacks: list | None) -> LLMResult:
        tier = TASK_TIERS.get(task, "fast")
        errors: list[str] = []
        previous: str | None = None
        for name in await self._budgeted_chain(ctx, agent, task):
            breaker = self.breakers.setdefault(name, Breaker())
            if breaker.is_open:
                errors.append(f"{name}: circuit open")
                continue
            provider = PROVIDERS[name]
            started = time.perf_counter()
            try:
                chaos.check_llm(name)
                if kind == "structured":
                    result = await provider.structured(tier, messages, schema, callbacks=callbacks, mock_fn=mock_fn)
                else:
                    result = await provider.text(tier, messages, callbacks=callbacks, mock_fn=mock_fn)
                breaker.record(True)
                cost = cost_usd(result.model, result.prompt_tokens, result.completion_tokens)
                self._log(ctx, agent, task, result, cost, True, previous, None)
                if ctx is not None:
                    ctx.add_cost(result.prompt_tokens + result.completion_tokens, cost, name)
                    if previous is not None:
                        msg = f"{previous} unavailable -> {name}"
                        if name == "mock":
                            msg += " (scripted MockLLM: last resort, flagged in report limitations)"
                        ctx.fallbacks.append(msg)
                        await ctx.emit(agent, "fallback", {"kind": "llm", "from": previous, "to": name,
                                                           "task": task, "errors": errors[-3:]})
                return result
            except Exception as exc:  # noqa: BLE001 - any provider error moves down the chain
                breaker.record(False)
                err = f"{name}: {type(exc).__name__}: {str(exc)[:200]}"
                errors.append(err)
                self._log(ctx, agent, task, LLMResult(None, name, provider.model_name(tier)
                                                      if hasattr(provider, "model_name") else name,
                                                      latency_ms=int((time.perf_counter() - started) * 1000)),
                          0.0, False, previous, err)
                previous = name
        raise AllProvidersFailed("; ".join(errors) or "no LLM provider configured")

    async def _budgeted_chain(self, ctx: RunContext | None, agent: str, task: str) -> list[str]:
        """The provider chain, cut to the scripted MockLLM once a run has spent its LLM budget.

        RUN_LLM_BUDGET_USD caps what one analysis can cost on paid providers (the deployed URL is
        public). Past the cap the run still finishes, on MockLLM, and the report says so.
        """
        chain = self.chain()
        budget = get_settings().run_llm_budget_usd
        if ctx is None or budget <= 0 or ctx.total_cost_usd < budget or chain == ["mock"]:
            return chain
        if not ctx.budget_exhausted:
            ctx.budget_exhausted = True
            msg = (f"LLM budget of US${budget:.2f} for this run reached (spent US${ctx.total_cost_usd:.4f}); "
                   "remaining steps use the scripted MockLLM")
            ctx.warnings.append(msg)
            ctx.fallbacks.append(msg)
            await ctx.emit(agent, "fallback", {"kind": "budget", "from": chain[0], "to": "mock", "task": task,
                                               "budget_usd": budget, "spent_usd": round(ctx.total_cost_usd, 6)})
        if not get_settings().llm_mock_last_resort:
            raise AllProvidersFailed(f"LLM budget of US${budget:.2f} for this run is used up")
        return ["mock"]

    def _log(self, ctx, agent, task, result: LLMResult, cost, ok, fallback_from, error) -> None:
        self.call_log.append({
            "analysis_id": ctx.run_id if ctx else None, "agent": agent, "task": task,
            "provider": result.provider, "model": result.model, "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens, "latency_ms": result.latency_ms,
            "cost_usd": cost, "success": ok, "fallback_from": fallback_from, "error": error,
        })

    async def structured(self, task: str, agent: str, messages: list[tuple[str, str]], schema: type[BaseModel],
                         ctx: RunContext | None = None, mock_fn: Callable | None = None,
                         callbacks: list | None = None) -> tuple[Any, LLMResult]:
        result = await self._run("structured", task, agent, messages, ctx, schema, mock_fn, callbacks)
        return result.value, result

    async def text(self, task: str, agent: str, messages: list[tuple[str, str]], ctx: RunContext | None = None,
                   mock_fn: Callable | None = None, callbacks: list | None = None) -> tuple[str, LLMResult]:
        result = await self._run("text", task, agent, messages, ctx, None, mock_fn, callbacks)
        return result.value, result

    def drain_log(self, run_id: str) -> list[dict[str, Any]]:
        mine = [c for c in self.call_log if c["analysis_id"] == run_id]
        self.call_log = [c for c in self.call_log if c["analysis_id"] != run_id]
        return mine


llm_router = LLMRouter()
