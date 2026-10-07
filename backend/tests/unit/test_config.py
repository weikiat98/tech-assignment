"""Settings: placeholder detection, provider aliases, env var aliases, chaos admin gating."""

import pytest

from app.config import Settings, is_configured


@pytest.mark.parametrize("value", [None, "", "   ", "REPLACE_ME", "sk-REPLACE_ME", "pk-lf-REPLACE_ME_x",
                                   "replace_me", " REPLACE_ME", "tvly-REPLACE_ME"])
def test_placeholders_are_not_configured(value):
    assert not is_configured(value)


@pytest.mark.parametrize("value", ["sk-proj-abc123", "AIzaSyExample", "tvly-real-key"])
def test_real_values_are_configured(value):
    assert is_configured(value)


def test_google_is_an_alias_for_gemini():
    s = Settings(llm_provider_order="openai, Google ,gemini")
    assert s.provider_order == ["openai", "gemini"]


def test_langfuse_base_url_alias(monkeypatch):
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
    assert Settings(_env_file=None).langfuse_host == "https://us.cloud.langfuse.com"


def test_values_are_stripped(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "  tvly-REPLACE_ME")
    s = Settings(_env_file=None)
    assert s.tavily_api_key == "tvly-REPLACE_ME" and not s.tavily_configured


@pytest.mark.parametrize(("env", "explicit", "allowed"), [
    ("local", None, True), ("test", None, True), ("aws", None, False), ("aws", True, True), ("local", False, False),
])
def test_chaos_admin_gating(env, explicit, allowed):
    assert Settings(_env_file=None, app_env=env, chaos_admin_enabled=explicit).chaos_admin_allowed is allowed


def test_database_url_composed_from_parts():
    s = Settings(_env_file=None, db_host="db.internal", db_user="policy", db_password="p@ss/word")
    assert s.database_url == "postgresql+asyncpg://policy:p%40ss%2Fword@db.internal:5432/policy"
