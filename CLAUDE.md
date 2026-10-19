# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Agentic Policy Data Analytics Platform" tech assessment (brief: `FSE_techassessment.txt`). **`plan.md` is the source of truth for every design decision** (decisions log in §18) — check it before making design choices and record new decisions there. `todo.md` lists open/unverified items (e.g. no recorded live Gemini/Langfuse result; AWS ECS was destroyed 15 Oct; redeploying takes about 30 min, see todo.md). The original deadline (Sun 4 Oct 2026) no longer applies; a live demo follows (script in plan.md §15). Git remote: `github.com/weikiat98/tech-assignment` (`main`).

Placeholder convention: every API key/env var in `.env.example` is `REPLACE_ME...`; the app treats any such value as "not configured" and falls back (MockLLM, keyless DuckDuckGo search, no Langfuse tracing) so it still runs end to end. Note the Windows system env may already have `OPENAI_API_KEY` set, which the app picks up (real spend) — set `LLM_MODE=mock` in `.env` to avoid that.

## Commands

Developed on Windows. Backend dependencies are managed with **uv** (decision 27): `backend/pyproject.toml` declares them (dev tools in the `dev` dependency group), `backend/uv.lock` pins them, `backend/.python-version` pins 3.12. No requirements.txt. Backend Makefile targets run through `uv run --locked`, so they are the same on every OS. Change deps with `uv add` / `uv lock --upgrade-package X` and commit `pyproject.toml` + `uv.lock` together. macOS setup steps are in README.md and DEPLOYMENT.md.

- `make install` — `uv sync --locked` (backend/.venv incl. dev tools) + `npm ci`
- `make up` / `make down` / `make logs` — full stack via docker compose (postgres+pgvector, gotenberg, migrate, api :8000, frontend/nginx :8080)
- `make dev-api` — backend with reload on :8000 (SQLite `backend/local.db` when no Postgres URL)
- `make dev-web` — Vite dev server on :5173, proxies to :8000
- `make cli Q="..."` — run one analysis in the terminal (`python -m app.cli`)
- `make samples` — rebuild MOM sample workbook and re-record source snapshots (`app.scripts.build_samples`)
- `make test` — `pytest -m "not contract and not llm"` with coverage (offline, MockLLM, temp SQLite; `tests/conftest.py` forces placeholder keys). Single test: `cd backend && uv run pytest tests/path.py::test_name`. Markers `contract` (live external services) and `llm` (costs money) are opt-in; `pytest tests/eval -s` prints the hallucination-detection table used in TESTING.md.
- `make lint` — `ruff check app tests` (line length 110, E501 ignored) + frontend `npm run lint`
- Frontend: `npm run typecheck`, `npm run build` (`tsc -b && vite build`), `npm test` (vitest)
- `make load-stack` then `make load` — Locust headless load test (the override `docker-compose.loadtest.yml` runs the api offline on MockLLM with tracing off, so it never hammers SingStat)
- `uv run python -m app.scripts.build_datagov_index` (from `backend/`) — rebuild the local Data.gov.sg catalogue index (`data/datagov_catalogue.json`); the v2 search API ignores its query
- `make aws-plan|aws-apply|aws-deploy|aws-pause|aws-resume|aws-destroy` — ECS Fargate via Terraform (`infra/terraform/aws`, `infra/scripts`); apply/destroy touch billable resources

## Architecture

**Backend** (`backend/app`, FastAPI + LangGraph, Python ≥3.11, async SQLAlchemy on Postgres or SQLite):

- `agents/graph.py` — the LangGraph pipeline: `interpret` → (ambiguous → `interrupt` for clarification, resumed via `Command`) → `plan` → `extraction` → `quality_gate` (no data → replan, max 2) → `analytics` → `write` ⇄ `verify` (rewrite loop, max 2) → END. Three agents: Coordinator, Extraction, Analytics. Checkpointing uses in-memory `MemorySaver`. Follow-up turns in a chat inherit sector/metric/years from earlier turns (`runner/followup.py` `history_text` feeds `interpret` and `write`; `FOLLOW_UP_RULE` in `prompts.py`); `agents/suggestions.py` builds the suggested follow-up questions deterministically (no LLM call).
- `agents/react.py` — provider-neutral ReAct loop; the model returns a structured `ReActStep` JSON (works on OpenAI, Gemini, and MockLLM) and every Thought/Action/Observation is emitted as an `AgentEvent`. `agents/mock_policies.py` holds the scripted MockLLM behaviour per agent; `prompts.py`/`vocab.py` hold prompts and sector vocabulary.
- `tools/` — tool wrappers the ReAct agents call (`extraction.py`, `analytics_tools.py`); `sources/` — adapters (SingStat MCP with REST fallback, MOM Excel, Data.gov.sg, internal mock) built on `sources/base.py` (retries, `SnapshotStore` of recorded raw responses, so `OFFLINE_MODE=true` serves everything from snapshots). All sources normalise to `CANONICAL_COLUMNS` (`core/models.py`).
- `llm/router.py` — `llm_router`: per-task model tier (`TASK_TIERS`), provider fallback chain (`LLM_PROVIDER_ORDER`, openai→gemini), circuit breaker, per-run cost budget (`RUN_LLM_BUDGET_USD`). `llm/providers.py` has the adapters.
- `verification/checks.py` — deterministic anti-hallucination checks on the drafted report: every number must match a cited `Fact`, citations must exist, years/sectors must be in the collected data. Failing claims trigger rewrite or are dropped.
- `quality/`, `analytics/` — data-quality validation/cleaning; stats (trends, correlations) and Plotly chart specs. `web/` — web search/fetch with SSRF guard, injection filter, grounding check, trust tiers. `export/` — Markdown, JSON/CSV/HTML/PDF (`files.py`; PDF rendered by Gotenberg) and Word (`docx.py`).
- `core/chaos.py` — runtime failure toggles for the demo (`CHAOS_FAIL_SOURCES`, `CHAOS_FAIL_LLM`, `CHAOS_INJECT_HALLUCINATION`, also `PUT /api/v1/admin/chaos`).
- `runner/task_runner.py` — analyses run as background asyncio tasks (`start`/`resume`/`cancel`); `core/events.py` — in-process event bus feeding `api/ws.py`. Both are deliberately single-replica with a small interface so arq/Redis and Redis pub/sub can replace them for scale-out; don't couple the API or graph to their internals.
- `api/` (REST under `/api/v1`, WebSocket, optional `APP_ACCESS_TOKEN` auth, slowapi rate limiting in `main_limiter.py`): `chats.py` is the primary entry point (a `Chat` is a conversation; each turn is an `Analysis` run, started via `runs.py`; `POST /chats`, `/chats/{id}/messages`, `/chats/{id}/turns/{n}/retry`, PATCH for rename/pin), `analyses.py` is the per-run API (events, summary, clarify, cancel, rerun, export), `meta.py` has config, provider list, source health and admin chaos. `db/` (models incl. `Chat`/`Analysis`/`AgentEventRow`, session, `python -m app.db.init` migrate step), `observability/` (Langfuse SDK v4 tracing, never verified against a live project).

**Frontend** (`frontend`, React 18 + TS + Vite, Tailwind 4, react-query, react-router, Plotly): a chat app. `pages/Home.tsx` (start) and `pages/Chat.tsx` (conversation); `Sidebar` lists/pins/renames chats; each question renders as a `Turn` with a live `Activity` view of agent events over WebSocket (`lib/useRunEvents.ts`, `lib/activity.ts`), result panels (insights/charts/data quality/report/plan, `ResultPanels`/`RunDetails`), clarification cards, follow-up suggestions, exports, and toast notifications (`lib/useRunToasts.ts`). Per-message options (web context, provider preference) live in `lib/useMessageOptions.ts`. Served by nginx in Docker (`nginx.conf.template`, `API_UPSTREAM`); the built `dist/` is baked into the image, so frontend changes need an image rebuild (`make up` does it via `--build`).

**Infra**: `.github/workflows/ci.yml` (uv + ruff + pytest, ESLint + Vitest + build, compose smoke test, GHCR images), `deploy-ecs.yml`, and `security.yml` (monthly CVE scan: pip-audit on uv.lock, npm audit, Trivy on both images; TESTING.md §9); Terraform for AWS ECS Fargate + CloudFront; Cloud Run is the documented alternative (plan.md §11).
