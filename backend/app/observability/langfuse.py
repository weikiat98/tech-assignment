"""Langfuse tracing (plan.md §4.3a). No-op unless all three LANGFUSE_* settings are real values.

One trace per analysis run (trace id seeded from the run id, session id = run id).
Every helper swallows its own errors: tracing must never break an analysis.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Iterator
from typing import Any

import structlog

from app.config import get_settings, is_configured

log = structlog.get_logger()

_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "[REDACTED_KEY]"),
    (re.compile(r"tvly-[A-Za-z0-9_-]{16,}"), "[REDACTED_KEY]"),
    (re.compile(r"AIza[0-9A-Za-z_-]{30,}"), "[REDACTED_KEY]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b[STFGM]\d{7}[A-Z]\b"), "[REDACTED_NRIC]"),  # Singapore NRIC/FIN pattern
]

_client: Any = None
_enabled: bool | None = None


def mask(data: Any, **_: Any) -> Any:
    """Redact secrets and personal data before traces leave the process."""
    if isinstance(data, str):
        for pattern, repl in _PATTERNS:
            data = pattern.sub(repl, data)
        return data
    if isinstance(data, dict):
        return {k: mask(v) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return type(data)(mask(v) for v in data)
    return data


def enabled() -> bool:
    global _client, _enabled
    if _enabled is not None:
        return _enabled
    s = get_settings()
    _enabled = all(is_configured(v) for v in (s.langfuse_public_key, s.langfuse_secret_key)) and bool(s.langfuse_host)
    if _enabled:
        try:
            from langfuse import Langfuse

            _client = Langfuse(public_key=s.langfuse_public_key, secret_key=s.langfuse_secret_key,
                               host=s.langfuse_host, sample_rate=s.langfuse_sample_rate, mask=mask)
        except Exception as exc:  # noqa: BLE001
            log.warning("langfuse_init_failed", error=str(exc))
            _enabled = False
    return _enabled


def trace_id_for(run_id: str) -> str | None:
    if not enabled():
        return None
    try:
        return _client.create_trace_id(seed=run_id)
    except Exception:  # noqa: BLE001
        return None


@contextlib.contextmanager
def run_trace(run_id: str, query: str, tags: list[str]) -> Iterator[list]:
    """Context manager yielding LangChain callbacks bound to this run's trace (empty when disabled)."""
    if not enabled():
        yield []
        return
    stack = contextlib.ExitStack()
    try:
        from langfuse import propagate_attributes
        from langfuse.langchain import CallbackHandler

        trace_id = _client.create_trace_id(seed=run_id)
        stack.enter_context(_client.start_as_current_observation(
            name="analysis-run", as_type="agent", trace_context={"trace_id": trace_id}, input={"query": query}))
        stack.enter_context(propagate_attributes(session_id=run_id, tags=tags, trace_name="policy-analysis"))
        handler = CallbackHandler()
    except Exception as exc:  # noqa: BLE001 - setup failure only; the run itself continues untraced
        log.warning("langfuse_trace_failed", error=str(exc))
        with contextlib.suppress(Exception):
            stack.close()
        yield []
        return
    try:
        yield [handler]
    finally:
        with contextlib.suppress(Exception):
            stack.close()


def score(run_id: str, name: str, value: float, comment: str | None = None) -> None:
    if not enabled():
        return
    try:
        _client.create_score(name=name, value=float(value), trace_id=_client.create_trace_id(seed=run_id),
                             data_type="NUMERIC", comment=comment)
    except Exception as exc:  # noqa: BLE001
        log.warning("langfuse_score_failed", error=str(exc))


def trace_url(run_id: str) -> str | None:
    if not enabled():
        return None
    try:
        return _client.get_trace_url(trace_id=_client.create_trace_id(seed=run_id))
    except Exception:  # noqa: BLE001
        return None


def flush() -> None:
    if enabled():
        with contextlib.suppress(Exception):
            _client.flush()
