"""Runtime chaos toggles used to demonstrate failure handling on cue.

Initialised from settings, mutable at runtime through the admin endpoint so the
live demo can flip a failure on without restarting the server.
"""

from dataclasses import dataclass, field

from app.config import get_settings


class ChaosError(RuntimeError):
    """Raised when a chaos toggle simulates an outage."""


@dataclass
class ChaosState:
    fail_sources: set[str] = field(default_factory=set)
    fail_llm: set[str] = field(default_factory=set)
    inject_hallucination: bool = False

    def check_source(self, source_id: str) -> None:
        if source_id in self.fail_sources:
            raise ChaosError(f"[chaos] simulated outage of source '{source_id}'")

    def check_llm(self, provider: str) -> None:
        if provider in self.fail_llm:
            raise ChaosError(f"[chaos] simulated outage of LLM provider '{provider}'")

    def as_dict(self) -> dict:
        return {
            "fail_sources": sorted(self.fail_sources),
            "fail_llm": sorted(self.fail_llm),
            "inject_hallucination": self.inject_hallucination,
        }


def _split(value: str) -> set[str]:
    return {v.strip() for v in value.split(",") if v.strip()}


_settings = get_settings()
chaos = ChaosState(
    fail_sources=_split(_settings.chaos_fail_sources),
    fail_llm=_split(_settings.chaos_fail_llm),
    inject_hallucination=_settings.chaos_inject_hallucination,
)
