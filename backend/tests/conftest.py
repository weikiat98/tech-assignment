"""Test configuration: keyless, offline and isolated.

Environment variables are set before any ``app`` import so the cached settings, the DB engine
and the chaos state are built for tests: scripted MockLLM, recorded source snapshots, mock web
search and a throwaway SQLite database. Nothing here calls a paid API.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="policy-tests-"))

os.environ.update({
    "APP_ENV": "test",
    "LLM_MODE": "mock",
    "OFFLINE_MODE": "true",
    "WEB_SEARCH_PROVIDER": "mock",
    "DATABASE_URL": f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}",
    "APP_ACCESS_TOKEN": "REPLACE_ME",
    # Override any real keys in the developer's environment: tests must never call a paid API.
    "OPENAI_API_KEY": "sk-REPLACE_ME",
    "GOOGLE_API_KEY": "REPLACE_ME",
    "TAVILY_API_KEY": "tvly-REPLACE_ME",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-REPLACE_ME",
    "LANGFUSE_SECRET_KEY": "sk-lf-REPLACE_ME",
    "CHAOS_FAIL_SOURCES": "",
    "CHAOS_FAIL_LLM": "",
    "CHAOS_INJECT_HALLUCINATION": "false",
    "RATE_LIMIT": "1000/minute",
})

sys.path.insert(0, str(Path(__file__).parent))

import pytest  # noqa: E402

from app.core.chaos import chaos  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_chaos():
    """Every test starts and ends with all failure toggles off."""
    chaos.fail_sources, chaos.fail_llm, chaos.inject_hallucination = set(), set(), False
    yield
    chaos.fail_sources, chaos.fail_llm, chaos.inject_hallucination = set(), set(), False
