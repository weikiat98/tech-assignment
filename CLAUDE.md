# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Agentic Policy Data Analytics Platform" tech assessment (brief: `FSE_techassessment.txt`). **`plan.md` is the source of truth for every design decision** (decisions log in §18) — check it before making design choices and record new decisions there. `todo.md` lists open/unverified items (e.g. Gemini/Langfuse never exercised live, AWS not deployed). The original deadline (Sun 4 Oct 2026) no longer applies; a live demo follows (script in plan.md §15). Git remote: `github.com/weikiat98/tech-assignment` (`main`).

Placeholder convention: every API key/env var in `.env.example` is `REPLACE_ME...`; the app treats any such value as "not configured" and falls back (MockLLM, keyless DuckDuckGo search, no Langfuse tracing) so it still runs end to end. Note the Windows system env may already have `OPENAI_API_KEY` set, which the app picks up (real spend) — set `LLM_MODE=mock` in `.env` to avoid that.

## Commands

Shell is Windows; the Makefile uses the backend venv at `backend/.venv/Scripts/`.

- `make up` / `make down` / `make logs` — full stack via docker compose (postgres+pgvector, gotenberg, migrate, api :8000, frontend/nginx :8080)
- `make dev-api` — backend with reload on :8000 (SQLite `backend/local.db` when no Postgres URL)
- `make dev-web` — Vite dev server on :5173, proxies to :8000
- `make cli Q="..."` — run one analysis in the terminal (`python -m app.cli`)
- `make samples` — rebuild MOM sample workbook and re-record source snapshots (`app.scripts.build_samples`)
- `make test` — `pytest -m "not contract and not llm"` with coverage (offline, MockLLM, temp SQLite; `tests/conftest.py` forces placeholder keys). Single test: `cd backend && .venv/Scripts/pytest tests/path.py::test_name`. Markers `contract` (live external services) and `llm` (costs money) are opt-in; `pytest tests/eval -s` prints the hallucination-detection table used in TESTING.md.
- `make lint` — `ruff check app tests` (line length 110, E501 ignored) + frontend `npm run lint`
- Frontend: `npm run typecheck`, `npm run build` (`tsc -b && vite build`), `npm test` (vitest)
- `make load-stack` then `make load` — Locust headless load test (the override `docker-compose.loadtest.yml` runs the api offline on MockLLM with tracing off, so it never hammers SingStat)
- `python -m app.scripts.build_datagov_index` (from `backend/`) — rebuild the local Data.gov.sg catalogue index (`data/datagov_catalogue.json`); the v2 search API ignores its query
- `make aws-plan|aws-apply|aws-deploy|aws-pause|aws-resume|aws-destroy` — ECS Fargate via Terraform (`infra/terraform/aws`, `infra/scripts`); apply/destroy touch billable resources

## Architecture

**Backend** (`backend/app`, FastAPI + LangGraph, Python ≥3.11, async SQLAlchemy on Postgres or SQLite):

- `agents/graph.py` — the LangGraph pipeline: `interpret` → (ambiguous → `interrupt` for clarification, resumed via `Command`) → `plan` → `extraction` → `quality_gate` (no data → replan, max 2) → `analytics` → `write` ⇄ `verify` (rewrite loop, max 2) → END. Three agents: Coordinator, Extraction, Analytics. Checkpointing uses in-memory `MemorySaver`.
- `agents/react.py` — provider-neutral ReAct loop; the model returns a structured `ReActStep` JSON (works on OpenAI, Gemini, and MockLLM) and every Thought/Action/Observation is emitted as an `AgentEvent`. `agents/mock_policies.py` holds the scripted MockLLM behaviour per agent; `prompts.py`/`vocab.py` hold prompts and sector vocabulary.
- `tools/` — tool wrappers the ReAct agents call (`extraction.py`, `analytics_tools.py`); `sources/` — adapters (SingStat MCP with REST fallback, MOM Excel, Data.gov.sg, internal mock) built on `sources/base.py` (retries, `SnapshotStore` of recorded raw responses, so `OFFLINE_MODE=true` serves everything from snapshots). All sources normalise to `CANONICAL_COLUMNS` (`core/models.py`).
- `llm/router.py` — `llm_router`: per-task model tier (`TASK_TIERS`), provider fallback chain (`LLM_PROVIDER_ORDER`, openai→gemini), circuit breaker, per-run cost budget (`RUN_LLM_BUDGET_USD`). `llm/providers.py` has the adapters.
- `verification/checks.py` — deterministic anti-hallucination checks on the drafted report: every number must match a cited `Fact`, citations must exist, years/sectors must be in the collected data. Failing claims trigger rewrite or are dropped.
- `quality/`, `analytics/` — data-quality validation/cleaning; stats (trends, correlations) and Plotly chart specs. `web/` — web search/fetch with SSRF guard, injection filter, grounding check, trust tiers. `export/` — Markdown/files/PDF (PDF rendered by Gotenberg).
- `core/chaos.py` — runtime failure toggles for the demo (`CHAOS_FAIL_SOURCES`, `CHAOS_FAIL_LLM`, `CHAOS_INJECT_HALLUCINATION`, also `PUT /api/v1/admin/chaos`).
- `runner/task_runner.py` — analyses run as background asyncio tasks (`start`/`resume`/`cancel`); `core/events.py` — in-process event bus feeding `api/ws.py`. Both are deliberately single-replica with a small interface so arq/Redis and Redis pub/sub can replace them for scale-out; don't couple the API or graph to their internals.
- `api/` (REST under `/api/v1`, WebSocket, optional `APP_ACCESS_TOKEN` auth, slowapi rate limiting in `main_limiter.py`), `db/` (models, session, `python -m app.db.init` migrate step), `observability/` (Langfuse SDK v4 tracing, never verified against a live project).

**Frontend** (`frontend`, React 18 + TS + Vite, Tailwind 4, react-query, react-router, Plotly): new analysis → live agent timeline over WebSocket → insights/charts/data quality/report/plan → history and exports. Served by nginx in Docker (`nginx.conf.template`, `API_UPSTREAM`).

**Infra**: `.github/workflows/ci.yml` and `deploy-ecs.yml`; Terraform for AWS ECS Fargate + CloudFront; Cloud Run is the documented alternative (plan.md §11).
