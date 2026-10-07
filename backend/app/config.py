"""Application settings.

Every secret defaults to a ``REPLACE_ME`` placeholder. Anything still holding a
placeholder is treated as "not configured", so the app runs end-to-end (on the
scripted MockLLM, keyless web search and recorded snapshots) before real keys exist.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_PREFIXES = ("REPLACE_ME", "sk-REPLACE_ME", "pk-lf-REPLACE_ME", "sk-lf-REPLACE_ME", "tvly-REPLACE_ME")
# Accepted spellings in LLM_PROVIDER_ORDER, mapped to the provider names in app.llm.providers.
PROVIDER_ALIASES = {"google": "gemini"}
BACKEND_ROOT = Path(__file__).resolve().parent.parent


def is_configured(value: str | None) -> bool:
    """True when a setting holds a real value (not empty, not a placeholder)."""
    if not value or not value.strip():
        return False
    value = value.strip()
    return not any(value.upper().startswith(p.upper()) for p in PLACEHOLDER_PREFIXES)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore", str_strip_whitespace=True)

    app_env: str = "local"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    # --- database -------------------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./local.db"
    # Alternative to DATABASE_URL (used on ECS, where RDS manages the password as its own secret).
    db_host: str | None = None
    db_port: int = 5432
    db_user: str | None = None
    db_password: str | None = None
    db_name: str = "policy"

    # --- LLM providers --------------------------------------------------------------
    llm_mode: str = "auto"  # auto | mock | live
    llm_provider_order: str = "openai,gemini"
    llm_mock_last_resort: bool = True
    llm_timeout_s: float = 60.0
    openai_api_key: str = "sk-REPLACE_ME"
    openai_model_strong: str = "gpt-4.1"
    openai_model_fast: str = "gpt-4.1-mini"
    google_api_key: str = "REPLACE_ME"
    gemini_model_strong: str = "gemini-2.5-pro"
    gemini_model_fast: str = "gemini-2.5-flash"
    run_llm_budget_usd: float = 0.50

    # --- Langfuse (tracing) ---------------------------------------------------------
    langfuse_public_key: str = "pk-lf-REPLACE_ME"
    langfuse_secret_key: str = "sk-lf-REPLACE_ME"
    # Langfuse's own docs call this LANGFUSE_BASE_URL; LANGFUSE_HOST is the older name. Both work.
    langfuse_host: str = Field("https://cloud.langfuse.com",
                               validation_alias=AliasChoices("langfuse_host", "langfuse_base_url"))
    langfuse_sample_rate: float = 1.0
    langfuse_capture_io: bool = True

    # --- data sources ---------------------------------------------------------------
    singstat_mcp_url: str = "https://chatwithsandra.singstat.gov.sg/mcp"
    singstat_rest_base: str = "https://tablebuilder.singstat.gov.sg/api/table"
    datagov_api_base: str = "https://api-production.data.gov.sg/v2/public/api"
    datagov_open_base: str = "https://api-open.data.gov.sg/v1/public/api"
    datagov_ckan_base: str = "https://data.gov.sg/api/action"
    datagov_api_key: str = "REPLACE_ME"  # optional; raises Data.gov.sg rate limits
    mom_excel_url: str = "REPLACE_ME"  # optional; falls back to the bundled sample workbook
    offline_mode: bool = False  # True = serve every source from recorded snapshots only
    snapshot_dir: str = str(BACKEND_ROOT / "data" / "snapshots")
    source_max_concurrency: int = 4

    # --- web search -----------------------------------------------------------------
    web_search_provider: str = "auto"  # auto | tavily | ddg | mock
    tavily_api_key: str = "tvly-REPLACE_ME"
    web_max_searches_per_run: int = 5
    web_max_fetches_per_run: int = 8
    web_fetch_timeout_s: float = 10.0
    web_fetch_max_bytes: int = 5_000_000

    # --- services -------------------------------------------------------------------
    gotenberg_url: str = "http://localhost:3000"

    # --- security -------------------------------------------------------------------
    app_access_token: str = "REPLACE_ME"  # when set, required on /api and /ws
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    rate_limit: str = "30/minute"

    # --- chaos toggles (demo failure handling) --------------------------------------
    chaos_fail_sources: str = ""  # e.g. "singstat_mcp,datagov"
    chaos_fail_llm: str = ""  # e.g. "openai"
    chaos_inject_hallucination: bool = False
    # PUT /admin/chaos can break a run for everyone, so it is off on shared deployments unless set explicitly.
    chaos_admin_enabled: bool | None = None

    @model_validator(mode="after")
    def _compose_database_url(self) -> "Settings":
        if self.db_host and self.db_user and self.db_password:
            self.database_url = (f"postgresql+asyncpg://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
                                 f"@{self.db_host}:{self.db_port}/{self.db_name}")
        return self

    @property
    def provider_order(self) -> list[str]:
        names = [p.strip().lower() for p in self.llm_provider_order.split(",") if p.strip()]
        return list(dict.fromkeys(PROVIDER_ALIASES.get(n, n) for n in names))

    @property
    def chaos_admin_allowed(self) -> bool:
        if self.chaos_admin_enabled is not None:
            return self.chaos_admin_enabled
        return self.app_env in ("local", "dev", "test", "ci")

    @property
    def tavily_configured(self) -> bool:
        return is_configured(self.tavily_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
