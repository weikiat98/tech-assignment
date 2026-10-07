"""LLM router: provider fallback chain, circuit breaker, chaos outage, per-run budget cap, cost."""

import pytest
from pydantic import BaseModel

from app.config import get_settings
from app.core.chaos import chaos
from app.core.run_context import RunContext
from app.llm import router as router_mod
from app.llm.costs import cost_usd
from app.llm.providers import LLMResult
from app.llm.router import AllProvidersFailed, LLMRouter


class Answer(BaseModel):
    text: str


class FakeProvider:
    def __init__(self, name: str, fail: bool = False, tokens: int = 1000):
        self.name, self.fail, self.tokens, self.calls = name, fail, tokens, 0
        self.available = True

    def model_name(self, tier):
        return f"{self.name}-{tier}"

    async def structured(self, tier, messages, schema, callbacks=None, mock_fn=None):
        self.calls += 1
        if self.fail:
            raise TimeoutError(f"{self.name} timed out")
        return LLMResult(schema(text=self.name), self.name, "gpt-4.1", self.tokens, self.tokens)

    async def text(self, tier, messages, callbacks=None, mock_fn=None):
        self.calls += 1
        if self.fail:
            raise TimeoutError(f"{self.name} timed out")
        return LLMResult(self.name, self.name, "gpt-4.1", self.tokens, self.tokens)


@pytest.fixture
def live(monkeypatch):
    """Two fake paid providers in the chain (openai, gemini) with the scripted mock as last resort."""
    s = get_settings()
    monkeypatch.setattr(s, "llm_mode", "auto")
    monkeypatch.setattr(s, "llm_provider_order", "openai,gemini")
    monkeypatch.setattr(s, "llm_mock_last_resort", True)
    monkeypatch.setattr(s, "run_llm_budget_usd", 0.50)
    fakes = {"openai": FakeProvider("openai"), "gemini": FakeProvider("gemini")}
    for name, p in fakes.items():
        monkeypatch.setitem(router_mod.PROVIDERS, name, p)
    return fakes


def ctx():
    return RunContext(run_id="r1", query="q")


async def ask(router, c=None):
    value, result = await router.structured("plan", "coordinator", [("user", "hi")], Answer, ctx=c,
                                            mock_fn=lambda: Answer(text="mock"))
    return value.text


def test_mock_mode_uses_only_mock(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_mode", "mock")
    assert LLMRouter().chain() == ["mock"]


def test_auto_without_keys_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_mode", "auto")
    assert LLMRouter().chain() == ["mock"]  # tests run with placeholder keys only


async def test_primary_serves_when_healthy(live):
    assert await ask(LLMRouter()) == "openai"
    assert live["gemini"].calls == 0


async def test_falls_back_to_secondary_and_records_it(live):
    live["openai"].fail = True
    router, c = LLMRouter(), ctx()
    assert await ask(router, c) == "gemini"
    assert c.fallbacks == ["openai unavailable -> gemini"]
    log = router.drain_log("r1")
    assert [(x["provider"], x["success"]) for x in log] == [("openai", False), ("gemini", True)]
    assert c.llm_providers_used == {"gemini"}


async def test_all_paid_providers_down_uses_mock_last_resort(live):
    live["openai"].fail = live["gemini"].fail = True
    c = ctx()
    assert await ask(LLMRouter(), c) == "mock"
    assert "MockLLM" in c.fallbacks[-1]


async def test_live_mode_without_last_resort_raises(live, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_mode", "live")
    live["openai"].fail = live["gemini"].fail = True
    with pytest.raises(AllProvidersFailed):
        await ask(LLMRouter())


async def test_circuit_opens_after_three_failures(live):
    live["openai"].fail = True
    router = LLMRouter()
    for _ in range(3):
        await ask(router)
    assert live["openai"].calls == 3
    await ask(router)
    assert live["openai"].calls == 3  # skipped while the circuit is open
    assert router.breakers["openai"].is_open


async def test_chaos_outage_moves_down_the_chain(live):
    chaos.fail_llm = {"openai"}
    assert await ask(LLMRouter()) == "gemini"
    assert live["openai"].calls == 0


async def test_budget_cap_switches_run_to_mock(live):
    c = ctx()
    c.total_cost_usd = 0.51
    router = LLMRouter()
    assert await ask(router, c) == "mock"
    assert await ask(router, c) == "mock"
    assert c.budget_exhausted
    assert sum("budget" in w for w in c.warnings) == 1  # reported once, not per call
    assert live["openai"].calls == 0


async def test_cost_accumulates_per_run(live):
    c = ctx()
    await ask(LLMRouter(), c)
    # gpt-4.1: 1,000 input tokens at $2/M + 1,000 output tokens at $8/M
    assert c.total_cost_usd == pytest.approx(0.01)
    assert c.total_tokens == 2000


def test_cost_table_and_unknown_model_default():
    assert cost_usd("gpt-4.1-mini", 1_000_000, 0) == pytest.approx(0.40)
    assert cost_usd("mock", 10_000, 10_000) == 0
    assert cost_usd("some-new-model", 1_000_000, 1_000_000) == pytest.approx(5.0)
