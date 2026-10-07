# Plan: Agentic Policy Data Analytics Platform

Source brief: `FSE_techassessment.txt`

---

## 1. What the brief asks for

The deliverable is a full-stack, multi-agent system. A policy researcher types a question in plain English, such as *"Analyse employment trends in the technology sector from 2020–2024"*. Agents then:

1. interpret and plan the work,
2. pull data from at least two Singapore government sources (SingStat, MOM, Data.gov.sg, mock internal DB),
3. validate and clean the data,
4. run real statistics on it,
5. return cited insights, charts and an exportable report.

The user watches the agents' reasoning live.

There are two submissions:
- **Section 1:** a GitHub repo containing the code, Docker setup, CI/CD, tests, `README.md`, `ARCHITECTURE.md`, `TESTING.md` and `DATA_SOURCES.md`. Section 1 is also shown in a 20-minute live demo.
- **Section 2:** an innovation essay of about 1–2 pages, saved as `INNOVATION.md`.

### Scoring weights, and where the effort goes

| Area | Weight | Implication for the plan |
|---|---|---|
| Development excellence | 50% | The **end-to-end path must work reliably** before anything else. Numbers must be correct, so the **LLM narrates and code computes**. |
| Agentic design | 25% | Use a real orchestration graph with ReAct loops, re-planning, graceful failure and clarification of ambiguous queries. |
| Testing & QA | 15% | Hallucination detection is the main differentiator. Design for testability from day 1 with a mock LLM and recorded HTTP. |
| DevOps & docs | 10% | One-command `docker compose up`, plus GitHub Actions and clear docs. |

### Guiding principles (taken from the brief's "Evaluation Philosophy")
- **Working over perfect.** Ship a thin vertical slice first, then deepen it.
- **Clear over complex.** Each added component must earn its place in the demo or the score.
- **Real data is messy.** Real APIs come first, with cached snapshots and mock data as a declared fallback. The fallback is a feature to show, not something to hide.

---

## 2. Requirements checklist (traceability)

Each line maps to a section of this plan. `[B]` marks a bonus item.

**1. Multi-agent system** → §4
- [ ] Coordinator, Extraction and Analytics agents (plus Report Writer and Verifier)
- [ ] Orchestration, delegation and autonomous collaboration

**2. Government data integration** → §5
- [ ] ≥2 sources (target: SingStat via **SingStat MCP**, Data.gov.sg, MOM and a mock internal DB)
- [ ] **Web search + extraction** by the Extraction agent, for data and context not covered by the official APIs (§5.4)
- [ ] CSV, Excel, JSON API, SQL and HTML (web) formats
- [ ] Error handling for API failures and missing data
- [ ] Data-quality validation and cleaning, shown visibly

**3. Analysis & insights** → §6
- [ ] Trends, patterns and correlations
- [ ] Policy-relevant insights
- [ ] Visualisations
- [ ] Structured reports with source citations
- [ ] `[B]` Forecasting

**4. Full-stack web app** → §7, §8
- [ ] React + TypeScript: natural-language input, live agent monitor, dashboard, history and export
- [ ] FastAPI: REST, async tasks, database and WebSocket

**5. Multi-cloud LLM** → §9
- [ ] ≥2 providers (OpenAI + Gemini, with Bedrock or Azure optional)
- [ ] Fallback between providers
- [ ] LLMs used for query interpretation, insights and report writing
- [ ] `[B]` Cost tracking

**6. Agentic framework** → §4
- [ ] LangGraph
- [ ] ReAct pattern
- [ ] Planning and decision-making
- [ ] Graceful failure handling

**7. Testing** → §10
- [ ] Unit tests: agents, tools and API
- [ ] Integration tests: multi-agent workflows
- [ ] LLM tests: hallucination, accuracy and consistency
- [ ] Data-quality tests
- [ ] Performance and load tests
- [ ] Docs: test plan, hallucination method, results and coverage

**8. DevOps** → §11
- [ ] Docker and Compose
- [ ] CI/CD
- [ ] Environment and secrets handling
- [ ] Deployment docs

**Remaining bonus items:**
- [ ] `[B]` Streaming → §7
- [ ] `[B]` RAG with a vector DB → §4.5
- [ ] `[B]` Performance and cost tracking → §9

**Submission docs and demo** → §12, §13, §14

---

## 3. Technology choices (with justification)

| Layer | Choice | Why |
|---|---|---|
| Backend API | **FastAPI** (Python 3.12), Pydantic v2 | Async-native, built-in WebSocket support, OpenAPI docs for free, typed schemas shared with the LLM's structured output |
| Agent framework | **LangGraph** | Explicit state graph (easy to explain in the demo), conditional edges for re-planning, built-in `interrupt` for clarification, checkpointing for resume and retry, event streaming |
| LLM clients | LangChain chat models (`langchain-openai`, `langchain-google-genai`, optional `langchain-aws`), wrapped in our own **`LLMRouter`** | We control the fallback order, circuit breaking, cost logging and the deterministic mock for tests |
| Task processing | **In-process asyncio task runner** (`asyncio.create_task` + run registry + in-memory event bus → WebSocket), with run state persisted to Postgres. *Stretch:* arq + Redis worker | Meets "asynchronous task processing" with the fewest moving parts for the Sunday deadline. The runner sits behind a `TaskRunner` interface, so swapping in arq + Redis (separate worker process, pub/sub to the WebSocket) is a contained change and is documented as the scale-out path |
| Database | **PostgreSQL 16** (pgvector image, so RAG can be added as a stretch) | Relational storage for runs, events, datasets and results. Using the pgvector image now means RAG needs no new service later |
| ORM / migrations | SQLAlchemy 2.0 (async); schema via `create_all` + seed (`python -m app.db.init`), Alembic once the schema must evolve in place | Standard and well understood (decision 11) |
| Data processing | pandas, NumPy, SciPy | Trend regression, correlations, YoY change, CAGR, linear-trend projection |
| Data validation | Plain pandas checks (`quality/checks.py`) | Every rule explicit and unit-tested, producing a quality report we can show (decision 11) |
| HTTP | httpx + tenacity | Async calls with retry, backoff and timeouts |
| MCP client | Official **`mcp`** Python SDK (`streamable_http_client` + `ClientSession`) | Connects to the **SingStat MCP**; discovery and metadata tools are exposed to the ReAct agent, data fetches are wrapped by the adapter (decision 11) |
| Web search | **Tavily** (search + extract APIs built for agents; free tier 1,000 credits/month) behind a `WebSearchProvider` interface; **DuckDuckGo** (`ddgs`, no key) as keyless fallback; `mock` provider for tests | Same pattern as the LLM router: provider-neutral, fallback, works without keys |
| Web extraction | httpx + **trafilatura** (main text), `pandas.read_html` (HTML tables), existing CSV/Excel parsers for linked files; *stretch:* pdfplumber for PDF tables | Turns pages into the canonical format, then the same quality pipeline runs on them |
| Frontend | **React 18 + TypeScript (Vite)**, React Router, Tailwind components, TanStack Query | The brief allows "Next.js/React" but names TypeScript explicitly, so TypeScript stays. A Vite single-page app is simpler than Next.js here: no SSR is needed, there are fewer framework rules, builds are faster, and it serves as static files from nginx. shadcn gives polished UI quickly |
| Charts | **Plotly** (backend emits figure JSON → `react-plotly.js`) | Analytics agent produces chart specs as data, so charts are testable and exportable and the frontend stays generic |
| Export | Markdown/JSON/CSV natively; PDF via **Gotenberg** (separate container: backend renders report HTML, POSTs it to Gotenberg's Chromium endpoint, gets a PDF back) | Keeps the backend image free of PDF system libraries. Chromium runs JavaScript, so the **interactive Plotly charts render in the PDF as-is**, whereas WeasyPrint has no JS and would need a separate static-image step (kaleido). Cost: one more ~1 GB container, which is acceptable in Compose |
| Testing | pytest, pytest-asyncio, respx, hypothesis, pytest-cov; Vitest + React Testing Library; **Locust**; *stretch:* Playwright | Covers unit, property, integration and load testing; browser E2E only if time allows |
| Quality | ruff, mypy, eslint, tsc, pre-commit | Code quality is part of the score |
| LLM / agent tracing | **Langfuse** (optional; Langfuse Cloud for dev, self-hostable) | Open-source and self-hostable, which suits government data residency. Native LangGraph callback, trace scores for verifier results, and cost/latency per call. See §4.3a |
| CI/CD | GitHub Actions → Amazon ECR → **AWS ECS (Fargate)**; Google Cloud Run documented as the alternative | Repo is on GitHub. Fargate runs the same containers as Compose with no servers to manage. Cloud Run is the GCP equivalent and fits the multi-cloud theme. See §11 |

---

## 4. Agent architecture

### 4.1 Agents

The brief requires 3 agents. We add 2 more because they directly support score criteria: the Report Writer handles report creation, and the Verifier handles hallucination detection.

| Agent | Role | Tools | LLM use |
|---|---|---|---|
| **Coordinator (Planner/Supervisor)** | Parses the query into a structured `ResearchIntent` (topic, sectors, metrics, geography, time range, comparison type). Decides whether to ask for clarification. Builds a `ResearchPlan` of tasks with dependencies, delegates tasks, monitors results and **re-plans** on failure or gaps. It may plan a `web` task when the question needs context or data outside the official catalogues | `singstat_search_tables` (MCP), `search_catalog` (local catalogue for the other sources), `ask_user` (interrupt) | Query interpretation and planning |
| **Data Extraction** | ReAct loop. Finds the right datasets per source, fetches them, normalises them to a canonical long format, runs quality checks and cleans. Falls back across sources and cache. **Searches the web and extracts data from pages** when official sources lack what is needed, or to locate source files (e.g. a MOM Excel link) | **SingStat MCP:** `singstat_search_tables`, `singstat_get_metadata`, `fetch_singstat` (wraps MCP `get_table_data` + normalise + snapshot). **Other sources:** `search_catalog`, `fetch_datagov`, `fetch_mom_excel`, `query_internal_db`. **Web:** `web_search`, `fetch_web_page`, `extract_web_data`. **Quality:** `validate_dataset`, `clean_dataset`, `load_snapshot` | Choosing datasets and series, mapping source columns to the canonical schema, deciding when the web is needed, extracting tables from web pages (with grounding checks), deciding retry or alternative on failure |
| **Analytics** | ReAct loop. Chooses analyses suited to the intent and executes them **deterministically in Python**. Every result is stored as a numbered **Fact**. Emits Plotly chart specs | `describe`, `trend_regression`, `yoy_change`, `cagr`, `share_breakdown`, `correlate`, `detect_anomalies`, `forecast`, `make_chart` | Choosing which analyses to run and interpreting results |
| **Report Writer** | Turns Facts into policy insights and a structured report (executive summary, key findings, sector analysis, limitations, citations). **Every claim must reference Fact IDs and source IDs** | `get_facts`, `get_sources`, `retrieve_related_reports` (RAG) | Insight generation and report creation |
| **Verifier (Critic)** | Checks each claim in the report. Numeric claims are compared with Facts within a tolerance. Citations must exist. Entities (sectors, years) must exist in the data. A cross-provider LLM judge scores faithfulness. Failing claims go back to the Writer, at most 2 times, and are otherwise dropped or flagged | `verify_numbers`, `verify_citations`, `verify_entities`, `llm_judge` | Faithfulness judging, done on a different provider from the Writer |

**Core design principle: "LLM reasons, code computes."** The LLM never does arithmetic that ends up in the report. All numbers come from tool outputs stored as Facts with IDs, such as `F12: ICT employment CAGR 2020–2024 = 4.8% [src: SINGSTAT:M182841, derived]`. (This mirrors the SingStat MCP's own attribution rule: only values returned by DOS are attributed to DOS, and derived values are labelled as computed by the platform.) This makes accuracy testable and is the backbone of hallucination detection.

### 4.2 Orchestration graph (LangGraph)

```
            ┌──────────────┐
  query ──▶ │  interpret   │──(ambiguous)──▶ [interrupt: clarify] ──┐
            └──────┬───────┘                                       │
                   ▼                                    ◀──────────┘
            ┌──────────────┐
            │    plan      │◀────────────────────────────┐
            └──────┬───────┘                             │ replan (gaps/failures,
                   ▼                                     │ max 2 iterations)
            ┌──────────────┐   parallel fan-out per     │
            │  extraction  │── source (Send API)         │
            └──────┬───────┘                             │
                   ▼                                     │
            ┌──────────────┐  insufficient data? ───────┘
            │  quality gate│
            └──────┬───────┘
                   ▼
            ┌──────────────┐
            │  analytics   │
            └──────┬───────┘
                   ▼
            ┌──────────────┐     fail (≤2)   ┌──────────┐
            │ report_write │◀────────────────│ verifier │
            └──────┬───────┘────────────────▶└────┬─────┘
                   │                              │ pass
                   ▼                              ▼
                               finalize (persist, embed, notify)
```

- **State:** a typed `AnalysisState` holding the intent, plan, task statuses, datasets (by reference, not raw frames), quality reports, facts, charts, draft report, verification results, errors and a cost tally.
- **Parallelism:** extraction tasks per source run concurrently through LangGraph's `Send`.
- **Checkpointing:** a Postgres checkpointer lets a failed run be **resumed** from the last good node, and lets clarification interrupts persist.
- **Each worker agent is a ReAct sub-graph:** Thought → Action (tool call) → Observation → … → Final answer. The step budget is 8 for extraction and 10 for analytics.

### 4.3 ReAct and observability

- Every Thought, Action (tool and arguments), Observation (truncated summary) and agent hand-off is emitted as an **`AgentEvent`** with these fields: `run_id`, `agent`, `step`, `type`, `content`, `ts`, `tokens` and `cost`.
- Events are stored in the `agent_events` table and published to the in-process event bus under topic `run:{id}`. The API relays them over WebSocket so the UI timeline shows reasoning live. With the stretch arq worker, the bus becomes Redis pub/sub on the same topic name.
- "Thought" content comes from a structured `reasoning` field that the model is asked to fill in. It is a short rationale, not hidden chain-of-thought.

### 4.3a Tracing with Langfuse (traceability, safety, observability)

There are two layers with different audiences. They complement each other rather than duplicate:

| Layer | Audience | Purpose |
|---|---|---|
| `AgentEvent` stream (above) | **Researcher**, in the app UI | Live, curated "what the agents are doing" timeline. Part of the product |
| **Langfuse** traces | **Engineer / auditor** | Full, nested trace of every graph node, LLM call (prompt, completion, model, provider, tokens, cost, latency) and tool call, kept for debugging, audit and evaluation |

**Integration:**
- Use the Langfuse LangChain/LangGraph `CallbackHandler`, passed in the graph's run config. It traces every node, LLM call and tool call automatically, so no per-agent tracing code is needed.
- **One trace per analysis run**: `trace_id` / `session_id` = `analysis_id`. Tags record the provider used, whether a fallback happened, `LLM_MODE` and the app version. Clarification and resume steps of the same run stay in one session.
- `LLMRouter` adds span metadata for **fallback events** (e.g. `fallback_from=openai, reason=timeout`), so a provider failover is visible in the trace tree.
- **Scores attached to traces:**
  - Verifier results: numeric-check pass rate, citation integrity, faithfulness score, and whether a rewrite was needed.
  - Data-quality score per dataset.
  - *Stretch:* the researcher's thumbs up/down from the UI.

  This turns Langfuse into a dashboard of hallucination and quality trends across runs.
- The run view in the UI has an **"Open trace"** link (shown only when Langfuse is configured).

**Safety controls:**
- A **masking function** in the Langfuse client redacts API keys, emails, NRIC-pattern IDs and anything matching configured PII patterns *before* traces leave the process.
- The trace sample rate and whether to capture raw prompt/completion text are configurable. For sensitive deployments, inputs and outputs can be switched off while metadata, latency and cost are still kept.
- **Self-hosting option** keeps traces inside the deployment boundary, which matters for government data residency. The hosted Langfuse Cloud is used only for development.

**Optional by design:**
- Langfuse is enabled only when `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_HOST` are set to real values. They follow the same `REPLACE_ME` placeholder rule as the LLM keys.
  - **Cloud and self-hosted use the same three variables.** A self-hosted Langfuse also issues a project public/secret key pair. Only `LANGFUSE_HOST` changes, e.g. `https://cloud.langfuse.com` vs `http://langfuse-web:3000`. The app code is identical either way.
- Without them, tracing is a no-op and the app works unchanged. Tests run with it off.
- The app's own `llm_calls` table and per-run cost stay the **source of truth for the UI and tests**. Langfuse cost is used for analysis across runs.

**Deployment of Langfuse itself:**
Both options give the same tracing; they differ in setup effort and where the data lives:

| | Langfuse Cloud | Self-hosted (local Docker) |
|---|---|---|
| Setup | Sign up, create project, copy 2 keys | `docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up` |
| Extra containers | None | 6: langfuse-web, langfuse-worker, Postgres, ClickHouse, Redis, MinIO (S3-compatible). A separate Postgres from the app's keeps them independent |
| Resources | None locally | Roughly 4 GB+ RAM for Docker on top of the app; ClickHouse is the heavy one |
| Keys | Copied from the Cloud UI | **Pre-seeded with no manual steps** through Langfuse's headless-init env vars (`LANGFUSE_INIT_ORG_ID`, `LANGFUSE_INIT_PROJECT_ID`, `LANGFUSE_INIT_PROJECT_PUBLIC_KEY`, `LANGFUSE_INIT_PROJECT_SECRET_KEY`, `LANGFUSE_INIT_USER_EMAIL`/`_PASSWORD`). The same values go into the app's `.env`, so tracing works on the first `up` with no clicking in the UI |
| Data location | Langfuse's servers (third party) | Stays on your machine (inside the deployment boundary in a real deployment) |
| Story for the government brief | Weaker | Stronger: "traces never leave our boundary" |

**Decision: Langfuse Cloud, Hobby (free) tier**, used by local Compose and by ECS.
- *Hobby limits:* 50k units/month (units = traces + observations + scores), 30 days of data access, 2 users, no credit card.
- *Expected usage:* one analysis run is roughly **60–120 units** (about 10 graph nodes, 15–25 LLM calls, 20–30 tool calls, plus about 5 scores). Two or three hundred dev and demo runs come to about **15–35k units**, inside the limit.
- *Protecting the limit:*
  - Tracing is **off in CI and pytest**, and **off for Locust load tests**. A load test alone could burn tens of thousands of units.
  - `LANGFUSE_SAMPLE_RATE` (default 1.0) can be lowered if usage approaches the cap.
  - Check the usage page in Langfuse on Sunday.
- *30-day retention:* fine for the deadline. Do a fresh run before the live demo so a recent trace is ready to show.
- *2 users:* invite a reviewer as the second user if they want to explore traces, or show traces during the demo.
- *Region:* pick the **EU or US** data region when creating the project. Langfuse Cloud has no Singapore region, which is one more reason the essay argues for self-hosting in production.
- *Data sent:* public open data, synthetic internal data and prompts. Nothing sensitive, so a third-party SaaS is acceptable for this assignment, and masking is on anyway.

**Self-hosted (documented, stretch):** `docker-compose.langfuse.yml` (based on Langfuse's official compose file) joins the app's Docker network. The backend reaches it at `http://langfuse-web:3000` and the UI is at `http://localhost:3000`. Switching is just a change of the three `LANGFUSE_*` variables. Self-hosting on ECS or Cloud Run (ClickHouse, S3, managed Redis/Postgres) is documented as the production path for government use and is not built for the deadline.

**Stretch:**
- **Langfuse prompt management:** versioned agent prompts, with the prompt version recorded on each trace.
- **Langfuse Datasets:** the golden eval set from §10.3 is stored as a Langfuse dataset, so evaluation runs on different models or providers can be compared side by side.

### 4.4 Failure handling (graceful degradation)

| Failure | Handling | Visible to user as |
|---|---|---|
| SingStat MCP unavailable or tool schema changed | Retry → **direct Table Builder REST API** (same tables, same resource IDs) → cached snapshot. A contract test flags tool-schema changes (§10) | Timeline event "SingStat MCP failed → REST API" |
| Web search provider down / quota used up | Tavily → DuckDuckGo → skip the web task and note it under Limitations | Timeline event + limitation note |
| Web page contains prompt-injection text | Page content is treated as data only (§5.4); suspicious instructions are flagged and stripped; extraction runs with no tools available | Warning badge on that source |
| Source API timeout/5xx | tenacity retry (3×, exponential backoff + jitter) → alternate source for the same metric → cached snapshot | Timeline event "SingStat failed → using cached snapshot from 2026-09-30"; report "Limitations" notes it |
| Dataset missing years / nulls | pandera flags it → cleaning strategy (interpolate ≤1 gap, otherwise mark as missing, never invent values) → quality score | Data Quality panel; caveat in report |
| No relevant dataset found | Coordinator re-plans with broadened terms; after 2 tries it returns a partial result that explains what is missing | Partial report + "data gap" notice |
| LLM provider error/rate limit/timeout | `LLMRouter` falls back to the next provider; a circuit breaker opens after N failures | Event "OpenAI unavailable → Gemini" |
| Malformed LLM output | Pydantic structured output → 1 repair retry → fallback provider | Transparent |
| Tool exception | Caught and returned to the agent as an error Observation, so the agent can choose another action | Timeline shows the error and the recovery |
| Agent exceeds step budget | Forced finish with best partial results | Flagged as partial |
| Ambiguous query ("how's the economy?") | Coordinator confidence < threshold → `interrupt` with suggested refinements; also supports "proceed with assumptions" | Clarification card in UI |
| Out-of-scope / unsafe query | Coordinator classifies the query and politely refuses | Message |

**Chaos switches for the demo:** `CHAOS_FAIL_SOURCES=singstat` and `CHAOS_FAIL_LLM=openai`, settable through env or an admin endpoint. These let the demo show failure handling on cue instead of hoping a failure happens.

### 4.5 RAG (bonus)
- **Dataset catalogue embeddings:** title, description, columns and source for every known dataset, stored in pgvector. The Coordinator and Extraction agents call `search_catalog("technology sector employment")` and get the top-k datasets back. **Scope reduced:** SingStat discovery (most of the catalogue) is handled by the MCP's `get_relevant_table_names`. `search_catalog` only covers Data.gov.sg, MOM and internal datasets, and a plain keyword/YAML search is enough there for the deadline. Embeddings stay a stretch item.
- **Past reports:** finished reports are embedded, so the Writer can cite "related previous analyses" and the UI can show similar past queries.

---

## 5. Data sources & ingestion

> **Phase-1 spike task:** confirm live endpoints, auth requirements, rate limits and the exact dataset or table IDs before coding the adapters. **SingStat is already verified through its MCP (§5.3).** The other IDs are candidates to verify.

| Source | Access method | Format | Candidate datasets |
|---|---|---|---|
| **DOS SingStat** | **Primary: SingStat MCP** (`https://chatwithsandra.singstat.gov.sg/mcp`, see §5.3). **Fallback:** Table Builder REST API (`tablebuilder.singstat.gov.sg/api/table/tabledata/{id}`), then snapshot | JSON (MCP tool results) | **Found through the MCP on 3 Oct 2026:** `M182841` Employment by Sector (annual, 2001–2025, source MOM, *data checked*); `M183901`/`M183891` Changes in Employment by Sector; `M651561` Employed Tech & Media Manpower by Sector; `M182081` Employed Residents by Industry & Occupation; `M183911` Retrenched Employees by Industry (quarterly); `M184071` Job Vacancies by Industry; `M016011` Compensation of Employees by Industry |
| **Data.gov.sg** | v2 public API (dataset metadata + `datastore_search` / poll-download for CSV) | JSON / CSV | MOM-published series mirrored there (unemployment rate, labour force); used for the **CSV path** and as a cross-source check against SingStat |
| **MOM Statistics** | Direct download of published Excel tables from stats.mom.gov.sg. The Extraction agent can **find the current download link by web search** | **Excel (.xlsx)** with multi-row headers and footnotes | Labour force, wages, retrenchment detail. Much MOM data is also reachable through Table Builder (the `dataSource` field reads "MINISTRY OF MANPOWER"), so this adapter is kept mainly to cover the Excel format the brief requires |
| **Internal (mock)** | Postgres schema `internal`, seeded with synthetic but plausible data | SQL | e.g. `workforce_programme_enrolments` (sector, year, trainees, placements) and `grant_disbursements`, which allow a "policy intervention vs outcome" analysis |
| **Web (open)** | `web_search` → `fetch_web_page` → `extract_web_data` (§5.4) | HTML, linked CSV/XLSX | Context and figures not in the catalogues, e.g. MOM Labour Market Report commentary, IMDA digital economy figures, news on tech retrenchments, with trust tiers applied |

Together these cover JSON API (MCP), CSV, Excel, SQL and HTML formats.

### 5.1 Adapter design
```python
class SourceAdapter(Protocol):
    source_id: str                      # "singstat" | "datagov" | "mom" | "internal" | "web"
    async def search(self, query: str) -> list[DatasetRef]
    async def fetch(self, ref: DatasetRef, params: FetchParams) -> RawDataset
    def normalise(self, raw: RawDataset) -> CanonicalFrame   # long format
```
- **Canonical long format:** `source_id, dataset_id, series, sector, period (date), frequency, value, unit, retrieved_at, url`. It makes all sources joinable, and the analytics code only has to handle one shape.
- **Sector harmonisation:** a mapping table aligns SSIC sector naming across sources, e.g. "Information & Communications" ≈ "ICT" ≈ "Technology". The LLM proposes mappings, but only validated entries from the map are used.
- **Snapshots:** every successful fetch is stored with its raw payload hash and timestamp in `dataset_snapshots`. A seeded snapshot set ships in `backend/data/snapshots/`, so the **demo works offline** and CI never hits live APIs.
- **Provenance:** every Fact carries `source_id` + `dataset_id` + URL + `retrieved_at` (+ `trust_tier` for web sources), and report citations are generated from these.

### 5.2 Data-quality pipeline (shown in the UI)
1. **Schema checks** (pandera): required columns, dtypes, units.
2. **Completeness:** expected periods vs present, and null ratio.
3. **Validity:** non-negative counts, percentages within 0–100, plausible ranges.
4. **Consistency:** duplicate rows; sector totals ≈ sum of sub-sectors within a tolerance; cross-source agreement on overlapping series. Divergence above 5% is flagged.
5. **Timeliness:** latest period available vs the requested range.
6. **Cleaning:** trim and normalise labels, parse MOM footnote markers such as `-`, `na` and `p` (provisional), unpivot wide→long, dedupe, interpolate only single gaps, and annotate every cleaning step.

The output is a `QualityReport` per dataset with a score, issues and actions taken. It is stored and displayed.

### 5.3 SingStat MCP integration (verified live, 3 Oct 2026)

**What it is:** DOS's official MCP server, a bridge to SingStat Table Builder (over 2,800 tables from 70 agencies). Endpoint: `https://chatwithsandra.singstat.gov.sg/mcp`. Details:
- **Transport:** streamable HTTP, stateless (no session ID).
- **Auth:** none needed.
- **Server:** `DOSTableBuilderMCP` v3.2.4, protocol `2025-06-18`.

**Tools** (checked with a live `tools/list` call):

| MCP tool | Input | Returns | Our use |
|---|---|---|---|
| `get_relevant_table_names` | `query_text` | Matching tables grouped by title → {frequency/seasonality: resource ID} | **Dataset discovery.** It replaces the planned local catalogue + embeddings for SingStat. A live test with "employment by industry information and communications" returned the tables listed in §5 |
| `get_table_metadata` | `resource_id` | Title, frequency, `dataSource` (e.g. MOM), `startPeriod`/`endPeriod`, `dataLastUpdated`, `footnote`, `row[]` {`seriesNo`, `rowText`, `uoM`, `footnote`} | Choosing series, **unit of measure**, valid date range, and **footnotes for caveats**. All of this feeds the quality checks and the report's Limitations section |
| `get_table_data` | `resource_id`, optional `seriesNoORrowNo`, `timeFilter` [`yyyy-mm`, `yyyy-mm`], `offset` | `row[]` with `columns[{key: period, value}]` | Actual data. **Capped at 3,000 rows**, so always filter by series and time, and page with `offset` |

**Integration design:**
- `langchain-mcp-adapters` loads the MCP tools.
  - **Search and metadata go straight to the agent** as `singstat_search_tables` and `singstat_get_metadata`. They are read-only and their outputs are small.
  - **`get_table_data` is wrapped** in our `SingStatMCPAdapter.fetch()`. It is not exposed raw, because every data fetch must go through normalisation → snapshot → quality checks → provenance. The agent calls `fetch_singstat(resource_id, series, time_range)`.
- **Our rules follow the tool descriptions:** always call metadata before data; never request periods outside `startPeriod`–`endPeriod`; always state units; surface row and table footnotes.
- **Data quirks seen in the live sample:**
  - Values are **strings**, e.g. `"451.2"`, so they are parsed and non-numeric markers handled.
  - Units vary by row, e.g. `Thousand`, so values are normalised to base units.
  - `seriesNo` is **hierarchical** (`3` Services → `3.4` Information And Communications), which enables a parent-vs-children consistency check.
  - Numbering has gaps (e.g. no `3.6`).
  - The footnote warns that "data may not add up to the total due to rounding", so the consistency check uses a tolerance.
- **Attribution:** the MCP asks that only values it returns be attributed to DOS, and derived values not be. Our Fact model already separates `source value` from `derived (method=…)`, and citations say "computed from DOS table M182841".
- **Resilience:**
  - Retry with backoff.
  - Fall back to the **Table Builder REST API** (same resource IDs, so the adapter swaps transport only), then to a snapshot.
  - A **concurrency limit** (e.g. 4 in flight) and a response cache, since no rate limit is published.
- **Contract test (nightly + in the Phase-A spike):** call `tools/list` and compare names and input schemas with the expected ones. The server advertises `tools.listChanged`, so its tools may change. This is a concrete example of handling "changing APIs".
- **Demo value:** "We use DOS's own MCP server, so the agent works with official tables through a standard protocol." This is a strong talking point for agentic design.

### 5.4 Web search & extraction (Extraction agent)

**When the agent uses it** (decided in its ReAct loop, or planned by the Coordinator as a `web` task):
1. The official sources (MCP, Data.gov.sg, MOM, internal) don't cover a needed metric or period.
2. Locating a source file, e.g. the current MOM Excel download link.
3. **Qualitative context** for the report, e.g. reasons behind a dip such as tech retrenchment waves, or policy announcements. This is kept clearly separate from the numeric Facts.

**Tools:**

| Tool | What it does |
|---|---|
| `web_search(query, recency?, domains?)` | `WebSearchProvider` (Tavily → DuckDuckGo → mock) returns title, URL, snippet and trust tier |
| `fetch_web_page(url)` | Safe fetch (guards below), then extracts the main text (trafilatura), HTML tables (`pandas.read_html`) and linked CSV/XLSX files, which go to the existing parsers. Returns a content summary + `page_id` and stores the raw content as a snapshot |
| `extract_web_data(page_id, target_schema_hint)` | LLM-assisted structured extraction of a table or figures into the canonical format, **followed by a deterministic grounding check** (below). Output goes through the normal quality pipeline |

**Trust tiers (by domain allowlist, configurable):**
- **Tier 1, official:** `*.gov.sg` (singstat, mom, data.gov.sg, mti, imda, mas). Can produce numeric Facts.
- **Tier 2, reputable statistical:** World Bank, ILO, IMF, OECD. Can produce numeric Facts, labelled as non-SG-government.
- **Tier 3, other** (news, blogs): **context only**. Never a numeric Fact; quoted as "reported by <source>" in the report.

The tier appears on citations and in the UI, and the Verifier rejects numeric claims that trace back to Tier 3.

**Anti-hallucination at extraction time (grounding check):**
- Every value the LLM extracts must **appear in the fetched page text**, after normalising for number formats such as `12,345` vs `12345`. The check is a string/number match, not an LLM judgement.
- Values that don't match are dropped and logged as `extraction_hallucination` events. This feeds the TESTING.md metrics.

**Safety guards** (important because web content is untrusted, and the app runs on ECS):
- **SSRF protection:**
  - Only `http(s)`.
  - Resolve DNS and **block private, loopback and link-local ranges**, including **`169.254.169.254` and `169.254.170.2` (AWS instance and ECS task metadata endpoints)**.
  - Re-check after redirects, with a maximum of 3 redirects.
- **Limits:** 10s timeout, 5 MB maximum size, content-type allowlist (HTML, CSV, XLSX, JSON, PDF), per-domain rate limit, polite User-Agent, respect `robots.txt`.
- **Prompt-injection defence:**
  - Page text is wrapped in explicit `<untrusted_content>` delimiters and never mixed into system instructions.
  - The extraction LLM call has **no tools bound**, so injected instructions can't trigger actions.
  - Heuristic detection of phrases like "ignore previous instructions" flags the page with a warning badge.
  - Output must match a strict Pydantic schema.
- **Budget:** at most N web searches and M page fetches per run (e.g. 5 and 8), enforced in the tool layer. This protects the Tavily free tier (1,000 credits/month).
- **Traceability:** every search, fetch and extraction is an `AgentEvent` and a Langfuse span, with URL, hash and tier.

**Keys and modes:** `TAVILY_API_KEY=REPLACE_ME` follows the same placeholder rule. With no key, it falls back to DuckDuckGo, which needs none. `WEB_SEARCH_PROVIDER=mock` serves recorded fixtures, used in tests and CI.

---

## 6. Analytics capabilities

All analytics are deterministic, unit-tested functions that return `Fact` objects plus optional chart specs:

- **Descriptive:** level, min/max, mean, latest value per series.
- **Change:** YoY and QoQ change, CAGR over the range, absolute change.
- **Trend:** OLS linear trend with slope, p-value and R², and a structural break or anomaly flag (z-score / rolling residual), e.g. the 2020 COVID dip.
- **Composition:** sector share of the total over time, and rank changes.
- **Correlation:** Pearson and Spearman with n and p-value, e.g. ICT employment vs ICT GDP, or programme enrolments vs placements. Small-n caveats are generated automatically.
- **`[B]` Forecast:** a statsmodels ETS/ARIMA 2–3 period forecast with confidence intervals, clearly labelled as a projection.
- **Charts** (Plotly JSON): multi-series line, indexed growth (base year = 100), stacked share, bar of YoY, correlation scatter with trendline, forecast fan.

---

## 7. Frontend (React + TypeScript, Vite)

### Routes (React Router)
1. **`/` New Analysis:** a natural-language query box with example prompts, optional advanced filters (sources, years), and an LLM-provider preference. Submitting navigates to the run page.
2. **`/analyses/:id` Run view:** a three-panel layout:
   - **Agent Activity** (left): a live timeline over WebSocket, grouped by agent, with Thought/Action/Observation steps, status chips, durations, token and cost counts, fallback and error events highlighted, and a plan view showing the task DAG with statuses.
   - **Results** (centre): tabs for *Insights* (cards with confidence and verification badge; hovering a number shows the Fact and source), *Charts* (interactive Plotly), *Data* (table preview + Quality report), and *Report* (streamed Markdown as it is written).
   - **Clarification card** when the run is waiting on `ask_user`.
3. **`/history`:** a searchable and filterable list of past analyses with status, duration and cost. Each entry can be re-run, duplicated or deleted.
4. **`/datasets`:** catalogue browser and source health (last fetch, status).
5. **Export** from the run view: PDF, Markdown, JSON (full structured result) and CSV (cleaned data + facts).

### Technical notes
- WebSocket hook with auto-reconnect. On reconnect it fetches missed events through `GET /events?after=seq`, so no events are lost.
- Report text is **streamed** token-by-token from the Writer (`[B]` streaming).
- Responsive layout: on mobile the panels collapse into tabs. Accessible, with keyboard navigation and ARIA labels.
- API types are generated from FastAPI's OpenAPI spec (`openapi-typescript`), so frontend and backend types stay in sync.
- In development, the Vite dev server proxies `/api` and `/ws` to FastAPI. In Docker, nginx serves the built static files and does the same proxying, so the browser only ever talks to one origin and no CORS setup is needed.
- **Deadline scope:** `/datasets`, history search/filter and mobile polish are stretch items. Query page, run view, history list and export are the MVP.

---

## 8. Backend API & data model

### REST + WS endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/analyses` | Create a run (query, options) → 202 + `id`; hands it to the `TaskRunner` |
| GET | `/api/v1/analyses` | List/search history (paginated) |
| GET | `/api/v1/analyses/{id}` | Full result: intent, plan, status, insights, facts, charts, report, quality, cost |
| GET | `/api/v1/analyses/{id}/events?after=` | Event replay |
| POST | `/api/v1/analyses/{id}/clarify` | Answer a clarification and resume the graph |
| POST | `/api/v1/analyses/{id}/cancel` | Cancel |
| POST | `/api/v1/analyses/{id}/rerun` | Re-run, optionally with a different provider |
| GET | `/api/v1/analyses/{id}/export?format=pdf\|md\|json\|csv` | Export |
| GET | `/api/v1/datasets`, `/api/v1/datasets/{id}` | Catalogue, snapshots and quality |
| GET | `/api/v1/sources/health` | Live source reachability |
| GET | `/api/v1/llm/providers` | Provider status, circuit-breaker state and cumulative cost |
| WS | `/ws/analyses/{id}` | Live `AgentEvent` + status + token stream |
| GET | `/healthz`, `/readyz` | Liveness and readiness (DB, Gotenberg) |

Errors use a consistent RFC 7807 problem+json body. Requests are validated by Pydantic. Rate limiting is per IP (slowapi). There is a request ID for correlation in logs.

### Database schema (PostgreSQL)
```
analyses(id PK, query, status[queued|running|awaiting_input|completed|partial|failed|cancelled],
         intent JSONB, plan JSONB, options JSONB, error TEXT,
         total_tokens INT, total_cost_usd NUMERIC, created_at, started_at, finished_at)
agent_events(id PK, analysis_id FK, seq INT, agent, type[thought|action|observation|handoff|error|fallback|status],
         content JSONB, tokens INT, cost_usd NUMERIC, created_at)          -- idx(analysis_id, seq)
datasets(id PK, source_id, external_id, title, description, columns JSONB, url, frequency, unit,
         embedding VECTOR(1536))
dataset_snapshots(id PK, dataset_id FK, retrieved_at, raw_hash, raw_path/bytea, row_count, is_fallback BOOL)
quality_reports(id PK, snapshot_id FK, analysis_id FK, score NUMERIC, issues JSONB, actions JSONB)
observations(snapshot_id FK, series, sector, period DATE, value NUMERIC, unit)   -- canonical data
facts(id PK, analysis_id FK, key TEXT, label, value NUMERIC, unit, method, params JSONB,
      source_snapshot_ids INT[])
charts(id PK, analysis_id FK, title, spec JSONB, fact_ids INT[])
reports(id PK, analysis_id FK, markdown TEXT, structured JSONB, verification JSONB,
        faithfulness_score NUMERIC, embedding VECTOR(1536))
insights(id PK, report_id FK, text, fact_ids INT[], source_ids TEXT[], verified BOOL, confidence)
llm_calls(id PK, analysis_id FK, agent, provider, model, prompt_tokens, completion_tokens,
          latency_ms, cost_usd, success BOOL, fallback_from TEXT, created_at)
internal.* (mock internal tables)
```
Plus LangGraph checkpoint tables, created by the checkpointer.

---

## 9. Multi-cloud LLM integration

### `LLMRouter`
- **Providers:** OpenAI (primary, e.g. `gpt-4.1`/`gpt-4o-mini` class), **Google Gemini** (secondary), optional AWS Bedrock (Claude) or Azure OpenAI as a third, and a **`MockLLM`** (deterministic, scripted responses) for tests and keyless demo mode. Model IDs live in config, not code.
- **Per-task routing policy** (configurable YAML):
  - `interpret/plan` → strong model
  - `react_step` → fast/cheap model
  - `report` → strong model
  - `judge` → **a different provider from the writer**, to avoid self-grading bias
- **Fallback chain:** primary → secondary → tertiary on timeout, 429, 5xx, safety block or invalid structured output after repair. A **circuit breaker** per provider (open after 3 consecutive failures, half-open after 60s) avoids paying the timeout cost repeatedly.
- **Structured outputs:** the same Pydantic models are used across providers. Provider differences are normalised in adapters, e.g. tool-calling formats.
- **Cost & performance tracking (bonus):** every call is logged to `llm_calls` with tokens, latency and cost (price table in config). Totals appear per run in the UI and in `/llm/providers`.
- **Caching:** an optional prompt-response cache keyed on (model, prompt hash), stored in a Postgres table, used for repeated demo queries and tests.
- **API keys (placeholders for now):** `.env.example` ships `OPENAI_API_KEY=sk-REPLACE_ME`, `GOOGLE_API_KEY=REPLACE_ME` and optional `AWS_*` / `AZURE_OPENAI_*`. At startup, the router treats any key that is empty or still starts with `REPLACE_ME`/`sk-REPLACE_ME` as "not configured" and skips that provider. With no real keys, `LLM_MODE=auto` falls back to `MockLLM`, so the whole app runs end-to-end before the real keys arrive. Dropping real keys into `.env` and restarting is the only change needed.
- **Consequence for the mock:** because the demo may run on `MockLLM` until keys arrive, the mock is **scripted for the sample queries in §14** (intent, plan, tool choices, insight text built from the real Facts). It is a proper test double, not a stub that returns "lorem ipsum".
- **Demo:** a toggle to force a provider failure shows a live fallback, with a timeline event and the cost attributed to the fallback provider.

---

## 10. Testing strategy (→ `TESTING.md`)

### 10.1 Pyramid & tooling
| Level | Scope | Tools | Notes |
|---|---|---|---|
| Unit: tools | Each analytics function (CAGR, YoY, regression, correlation) against hand-computed fixtures; adapters' `normalise` on recorded payloads; cleaning functions | pytest, **hypothesis** (property tests, e.g. "cleaning never invents values", "CAGR of a constant series is 0") | Fast, no network |
| Unit: agents | Each agent node with `MockLLM` scripted responses: correct tool choice, handling tool errors, step-budget exit, structured-output repair | pytest-asyncio | Deterministic |
| Unit: API | Endpoint contracts, validation errors, 404s, problem+json, WS message shape | httpx `AsyncClient`, FastAPI TestClient | |
| Unit: LLM router | Fallback order, circuit breaker transitions, cost accounting, retry on invalid JSON | pytest with fake providers | |
| Integration: workflows | Full graph with MockLLM + **respx-recorded source responses**: happy path, source failure → fallback to snapshot, LLM failure → provider fallback, ambiguous query → interrupt → resume, verifier rejection → rewrite loop, partial result | pytest + Postgres via Docker (testcontainers or CI services) | Core proof that agents collaborate |
| Data quality | pandera schemas per source; fixture datasets with known defects (missing years, dup rows, `na` markers, unit mismatch, MCP string values, hierarchical parent ≠ sum of children beyond rounding tolerance) must be detected and handled as expected | pytest + pandera | |
| SingStat MCP | Unit: adapter normalisation on **recorded MCP responses** (search/metadata/data JSON saved during the spike). Contract: live `tools/list` → expected tool names and input schemas | pytest; the contract test runs nightly and on demand (`-m contract`), not in PR CI | Detects upstream changes to the tools |
| Web tools | **SSRF:** private IPs, `169.254.169.254`, redirects to internal hosts are all blocked. **Injection:** a fixture page with "ignore previous instructions…" is flagged, and the extraction output is unaffected and schema-valid. **Grounding:** an extracted value not present in the page is dropped. **Trust tiers:** a Tier-3 number never becomes a Fact. Provider fallback Tavily → DDG → skip; per-run budget enforced | pytest + respx fixtures, `mock` search provider | Covers safety and the "messy real-world data" angle |
| LLM evals (live, opt-in) | Golden question set run against real providers | pytest marker `@pytest.mark.llm`, run nightly/manual in CI | Kept out of PR CI because of cost and nondeterminism |
| Frontend unit | Components (timeline, insight card, chart wrapper), WS hook reconnect | Vitest + RTL + MSW | |
| E2E *(stretch)* | Submit query → see events → see charts → export | **Playwright** against the compose stack with MockLLM | Only if Sunday allows; otherwise an API-level E2E test (create run → WS events → export) covers the flow |
| Performance / load | Concurrent run creation, WS fan-out, history listing p95; analytics function benchmarks | **Locust** (API + WS), pytest-benchmark | Report p50/p95 and throughput in TESTING.md |

**Coverage target:** ≥80% backend lines and ≥70% frontend. The CI artefact contains the HTML coverage report and a badge.

### 10.2 Hallucination detection methodology (key differentiator)
Several layers, with each insight tagged by result:

1. **Grounded generation by construction:** the Writer only receives Facts, each with an ID, and must output `claims[{text, fact_ids, source_ids}]`.
2. **Numeric claim verification (deterministic):** extract every number, percentage and year from claim text (regex + unit parsing) and match it to a cited Fact value within a tolerance (rounding-aware, e.g. 4.8% vs 0.0481). An unmatched number fails the check.
3. **Citation integrity:** every cited `fact_id` and `source_id` must exist in this run, and the cited fact must support the claim, checked by series/sector overlap.
4. **Entity grounding:** sectors, years and metrics named in claims must exist in the extracted data. This catches "invented" sectors or out-of-range years.
5. **Cross-provider LLM-as-judge:** a judge on another provider scores each claim's faithfulness to its cited facts (supported / partially / unsupported), giving a run-level faithfulness score.
6. **Self-consistency:** for evaluation, run the same query N=5 times and measure (a) intent and plan agreement, (b) overlap of the set of facts used, (c) semantic similarity of key findings, (d) variance of numeric claims (which should be 0 because the numbers come from tools).
7. **Adversarial tests:** inject a deliberately wrong number or fake citation into a draft and assert the verifier catches it. Ask about data that doesn't exist (e.g. "2030 actuals") and assert a refusal or limitation statement, not fabrication.

**Metrics reported:** claim-level precision of the verifier on a labelled set, hallucination rate before vs after verification, faithfulness score distribution, and consistency scores.

### 10.3 Accuracy validation
- A **golden dataset** of 10–15 questions with expected Facts computed independently in a notebook or spreadsheet, e.g. "ICT employment change 2020→2024". The pipeline output must match within tolerance.
- Intent-parsing accuracy on 30 labelled queries (sector, years, metric extracted correctly).

---

## 11. DevOps & deployment

- **Dockerfiles:** multi-stage, non-root, slim images.
  - `backend/Dockerfile` uses uv for dependency install.
  - `frontend/Dockerfile`: stage 1 runs `vite build`; stage 2 is `nginx:alpine` serving `dist/` and proxying `/api` and `/ws` to the backend.
- **`docker-compose.yml`:** `postgres` (pgvector image), `api`, `frontend`, `gotenberg` (`gotenberg/gotenberg:8`, internal network only, not exposed to the host), and a one-shot `migrate` (Alembic + seed: catalogue, internal mock data, snapshots). Health checks and `depends_on: condition: service_healthy`. *Stretch:* `redis` + `worker` if arq is adopted.
- **Profiles:** `docker compose up` runs the full app; `--profile load` adds Locust.
- **Environment & secrets:**
  - `pydantic-settings` loads `.env` (committed `.env.example` with `REPLACE_ME` placeholders, `.env` git-ignored).
  - `LLM_MODE=auto|mock|live`: `auto` (default) uses real providers whose keys are set and falls back to `MockLLM` when none are, so reviewers can run without keys.
  - Secrets come only from env or Docker secrets, never logged, and are redacted in event content.
  - In CI they come from GitHub Secrets. In the cloud they come from AWS Secrets Manager (ECS) or GCP Secret Manager (Cloud Run). See §11.1.
- **CI** (`.github/workflows/ci.yml`, on PR + push):
  1. Backend: ruff, mypy, pytest (unit + integration with service containers), coverage upload.
  2. Frontend: eslint, tsc, vitest, build.
  3. Smoke test: `docker compose up` (mock LLM) → hit `/readyz` → create a run → assert it completes. *Stretch:* Playwright.
  4. Docker build; on `main`, push images tagged with the git SHA to **Amazon ECR** (and to GHCR, so reviewers can pull without AWS access).
  5. *Stretch:* security scans (`pip-audit`, `npm audit`, Trivy, gitleaks).
- **CD:** see §11.1 (ECS, primary) and §11.2 (Cloud Run, alternative). Live LLM evals run on a nightly workflow (stretch).
- **Observability:**
  - Structured JSON logs (structlog) with `run_id` and `request_id`, shipped to CloudWatch Logs on ECS and Cloud Logging on Cloud Run.
  - **Langfuse** traces for agents and LLM calls (§4.3a).
  - `/healthz` and `/readyz` are used by the load balancer health checks.

### 11.1 Primary deployment target: AWS ECS on Fargate (`ap-southeast-1`, Singapore)

**Status: in scope and actually deployed** to a personal AWS account. The live demo still runs on local Compose as the primary path, with the ECS URL shown as "it is deployed for real". If the network or the cloud misbehaves during the demo, nothing breaks.

```
                Internet
                   │ HTTPS (default *.cloudfront.net certificate, no domain needed)
            ┌──────▼──────┐
            │ CloudFront  │  (WebSocket supported; forwards all headers/cookies for /api, /ws)
            └──────┬──────┘ HTTP
            ┌──────▼──────┐  SG: inbound only from the CloudFront managed prefix list
            │     ALB     │  /api/*, /ws/*  → api target group   (idle timeout raised to 300s)
            │             │  /*             → frontend target group
            └──┬───────┬──┘
   ┌───────────▼──┐  ┌─▼────────────────────────────────┐   public subnets, public IP,
   │ frontend svc │  │ api svc (desired count = 1)       │   SG: inbound only from the ALB
   │ nginx + SPA  │  │  task: [api container]            │
   └──────────────┘  │        [gotenberg sidecar :3000]  │──▶ OpenAI / Gemini APIs
                     └──────────────┬────────────────────┘──▶ Langfuse Cloud (or off)
                                    │ private subnets (no internet route)
                             ┌──────▼──────┐
                             │ RDS Postgres│ (pgvector extension available)
                             │ 16          │
                             └─────────────┘
```

- **HTTPS without buying a domain:** an ACM certificate needs a domain name, and the ALB's own DNS name can't get one. Putting **CloudFront** in front gives HTTPS on a `*.cloudfront.net` URL for free, and CloudFront supports WebSockets. The ALB only accepts traffic from CloudFront. *(Confirmed: no custom domain, so CloudFront is used.)*
- **Networking choice for a personal account:** Fargate tasks run in **public subnets with a public IP**, and their security groups only allow traffic from the ALB. That lets them pull from ECR and call the LLM APIs **without a NAT gateway**, which would cost about US$40+/month on its own. RDS sits in private subnets with no internet route. *Production note (DEPLOYMENT.md):* move tasks to private subnets with a NAT gateway or VPC endpoints.
- **Access protection** (the deployed app calls paid LLM APIs on your keys, so a public URL invites abuse):
  - The app requires a shared **`APP_ACCESS_TOKEN`** (FastAPI middleware on `/api` and `/ws`, plus a simple passphrase screen in the UI). It is off locally and on in AWS.
  - Rate limiting is already planned (slowapi).
  - A per-run LLM budget cap.
  - A **monthly spending limit set in the OpenAI and Gemini consoles** as a last line of defence.
- **Images:** stored in ECR. Each image is tagged with the git SHA, so deploys are immutable. Lifecycle policy keeps the last 10.
- **Gotenberg runs as a sidecar** in the api task definition and is reached at `localhost:3000`. That avoids service discovery and keeps it private.
- **Database:** RDS for PostgreSQL 16 (`db.t4g.micro`, 20 GB, single-AZ) in private subnets, with the security group only allowing the api tasks. **`manage_master_user_password = true`**: RDS generates the password and keeps it in Secrets Manager, so it never appears in Terraform state or in the repo.
- **Langfuse on ECS:** a self-hosted Langfuse on your laptop can't be reached from AWS. In ECS, either use Langfuse Cloud keys or leave tracing off. This depends on the Langfuse choice that is still open (§18).
- **Migrations:** each deploy runs `alembic upgrade head` + seed as a **one-off ECS task** (`aws ecs run-task`, same image, different command) before the service update.
- **Secrets:**
  - LLM keys, Langfuse keys and the DB URL live in **AWS Secrets Manager**, referenced through the task definition's `secrets` block, so they are never in the image or in plain env vars.
  - GitHub Actions authenticates to AWS with **OIDC** (`aws-actions/configure-aws-credentials` assuming an IAM role), so no long-lived AWS keys are stored in GitHub.
- **Deploy workflow** (`deploy-ecs.yml`, triggered by `workflow_dispatch` or a `v*` tag):
  1. OIDC login.
  2. Build and push to ECR.
  3. Render the task definitions with the new image (`amazon-ecs-render-task-definition`).
  4. Run the migration task.
  5. `amazon-ecs-deploy-task-definition` with `wait-for-service-stability`.
  6. Smoke-test `/readyz` through the CloudFront URL.
  7. Rely on the ECS deployment circuit breaker for automatic rollback.
- **Infrastructure as code: Terraform (now in scope)**, in `infra/terraform/aws/`. On a personal account, a clean, complete **`terraform destroy`** matters more than saving the 2–3 hours it takes to write. It is also a reproducible artefact for the DevOps score.
  - **Files:**
    - `network.tf`: VPC, 2 public + 2 private subnets across 2 AZs, no NAT.
    - `security.tf`: security groups for CloudFront→ALB→tasks→RDS.
    - `ecr.tf`: ECR repositories.
    - `rds.tf`: the database.
    - `secrets.tf`: secret *containers* only. Values are set out-of-band with `aws secretsmanager put-secret-value`, so keys never enter Terraform state.
    - `iam.tf`: task execution role, task role, and the **GitHub OIDC provider + deploy role** (trust scoped to this repo's `main` branch and tags).
    - `alb.tf`, `cloudfront.tf`.
    - `ecs.tf`: cluster, services, initial task definitions, CloudWatch log groups with 7-day retention.
    - `budget.tf`: **AWS Budgets email alerts** at 50%/80%/100% of a monthly limit, e.g. US$30.
  - **State:** a local state file (git-ignored) is fine for a personal, single-user project. An S3 backend with a lock is documented as the team setup.
  - **No drift fights:** the ECS services use `lifecycle { ignore_changes = [task_definition] }`. Terraform owns the infrastructure; the deploy workflow owns new task-definition revisions.
  - **Safety rule:** `terraform apply` and `terraform destroy` create or remove billable resources, so they are **only ever run with your explicit go-ahead**. `terraform plan` output is reviewed first.
- **Make targets:** `make aws-plan`, `make aws-apply`, `make aws-deploy` (build, push and deploy from your machine, as a fallback to the pipeline), `make aws-pause` (ECS desired count 0 + stop RDS), `make aws-resume`, `make aws-destroy`.
- **Important constraint, documented honestly:**
  - The in-process `TaskRunner` and event bus mean the **api service must run as 1 task**. A WebSocket on task B would not see events from a run on task A.
  - Scaling out means adding **ElastiCache Redis + an arq worker service**, the stretch path in §3. Events then go through Redis pub/sub, so any api task can serve any WebSocket.
  - The architecture is designed for this switch, but it is not built for the deadline.
- **Cost (rough estimate; confirm with the AWS Pricing Calculator):**

  | Item | Approx. US$/day running 24/7 |
  |---|---|
  | Fargate api task (1 vCPU / 3 GB incl. Gotenberg) | ~1.6 |
  | Fargate frontend task (0.25 vCPU / 0.5 GB) | ~0.4 |
  | ALB | ~0.6 |
  | RDS `db.t4g.micro` + 20 GB | ~0.7 |
  | Public IPv4 addresses (ALB + tasks), Secrets Manager, CloudWatch, CloudFront | ~0.5 |
  | **Total** | **≈ US$3–4/day (~US$100/month)** |

  New accounts may get free-tier credits, which can cover some of this. **Pause** between sessions with `make aws-pause`. Leaving only the ALB and stopped RDS storage costs roughly US$1/day. **Destroy** after the evaluation. Note that RDS restarts automatically after 7 days stopped.

#### One-time account setup (you, today, before any code is ready)
New-account verification can take from minutes to hours, so this runs in parallel with block A:
1. Create the account with region **`ap-southeast-1`**, and turn on **MFA for the root user**. After this the root user is not used again.
2. Create an admin identity for daily use. The preferred way is **IAM Identity Center** user + `AdministratorAccess` permission set, then `aws configure sso`. A plain IAM user with MFA also works.
3. **AWS Budgets:** a monthly budget (e.g. US$30) with email alerts, set up *before* creating anything else.
4. Install **AWS CLI v2** and **Terraform ≥ 1.6** locally, then confirm `aws sts get-caller-identity` works with the new profile.
5. Set spending limits in the OpenAI and Google AI consoles once the keys exist.

### 11.2 Alternative deployment target: Google Cloud Run (`asia-southeast1`, Singapore)

Documented and kept deployable with a separate manual workflow, `deploy-cloudrun.yml`, but not the primary path.

| Concern | Cloud Run equivalent |
|---|---|
| ECR | Artifact Registry |
| ECS service + sidecar | Cloud Run service with **multi-container (sidecar)**: api + gotenberg |
| ALB path routing | The frontend is a separate Cloud Run service, and its nginx proxies `/api` and `/ws` to the api service URL (`API_UPSTREAM` env, via nginx `templates/` envsubst). Alternatively, a global HTTPS load balancer with URL map |
| RDS | Cloud SQL for PostgreSQL (pgvector supported), via the Cloud SQL connector |
| Secrets Manager | Secret Manager, mounted as env vars |
| OIDC role | Workload Identity Federation for GitHub Actions |
| Migration task | **Cloud Run Job** running the same image with the alembic command |

**Cloud Run caveats for our design:**
- Background tasks keep running after the POST returns only with **instance-based billing ("CPU always allocated")**.
- Set **min-instances = 1 and max-instances = 1** for the same single-replica reason as ECS.
- Enable session affinity for WebSockets. The request timeout (up to 60 minutes) covers long WebSocket sessions, and the client reconnect + event replay (§7) handles drops.

### 11.3 Environment matrix
| Env | Where | LLM | Langfuse | Data |
|---|---|---|---|---|
| local | `docker compose up` | `auto` (mock until keys) | Langfuse Cloud Hobby (off until keys are set) | live APIs + snapshot fallback |
| ci | GitHub Actions | `mock` | off | snapshots only (respx) |
| aws (primary) | ECS Fargate | `live` | Langfuse Cloud Hobby (self-hosted in a real production deployment) | live + fallback |
| gcp (alt) | Cloud Run | `live` | same | live + fallback |

---

## 12. Repository structure

```
/
├── README.md  ARCHITECTURE.md  TESTING.md  DATA_SOURCES.md  DEPLOYMENT.md  INNOVATION.md
├── docker-compose.yml  docker-compose.langfuse.yml  .env.example  Makefile  .pre-commit-config.yaml
├── .github/workflows/{ci.yml,deploy-ecs.yml,deploy-cloudrun.yml,nightly-llm-eval.yml}
├── infra/
│   ├── terraform/aws/  # network, security, ecr, rds, secrets, iam (+GitHub OIDC), alb,
│   │                   # cloudfront, ecs (api+gotenberg sidecar, frontend, migrate task), budget,
│   │                   # variables.tf, outputs.tf (CloudFront URL, ECR URIs, role ARN)
│   └── gcp/            # service-api.yaml (multi-container), service-frontend.yaml, job-migrate.yaml, SETUP.md
├── backend/
│   ├── pyproject.toml  Dockerfile  alembic/
│   ├── app/
│   │   ├── main.py  config.py  deps.py
│   │   ├── api/            # routers: analyses, datasets, sources, llm, ws
│   │   ├── agents/
│   │   │   ├── graph.py    # LangGraph assembly
│   │   │   ├── state.py
│   │   │   ├── coordinator.py  extraction.py  analytics.py  writer.py  verifier.py
│   │   │   ├── react.py    # shared ReAct sub-graph builder
│   │   │   └── prompts/
│   │   ├── tools/          # catalog, fetch_*, web_*, quality, cleaning, analytics, charts
│   │   ├── sources/        # singstat_mcp.py (+ REST fallback) datagov.py mom.py internal.py base.py
│   │   ├── mcp/            # MCP client config (servers.yaml), tool loading via langchain-mcp-adapters
│   │   ├── web/            # search providers (tavily, ddg, mock), safe_fetch (SSRF guards),
│   │   │                   # extract (trafilatura, read_html), grounding check, trust tiers, injection filter
│   │   ├── llm/            # router.py providers/ (openai, gemini, bedrock, mock) costs.py
│   │   ├── analytics/      # pure functions: trends.py stats.py forecast.py
│   │   ├── quality/        # pandera schemas, checks, cleaning
│   │   ├── verification/   # numeric, citation, entity, judge
│   │   ├── events/         # publisher, schemas
│   │   ├── db/             # models.py session.py repositories/
│   │   ├── runner/         # TaskRunner interface, asyncio implementation, event bus
│   │   ├── observability/  # langfuse.py (handler factory, masking, scores), logging.py
│   │   └── export/         # md, csv, json, html template + Gotenberg client for pdf
│   ├── data/{snapshots/,catalog.yaml,sector_map.yaml,internal_seed/}
│   └── tests/{unit/,integration/,data_quality/,llm_eval/,load/,fixtures/}
└── frontend/
    ├── package.json  Dockerfile  vite.config.ts  nginx.conf  tsconfig.json  index.html
    ├── src/{main.tsx,App.tsx,routes.tsx}
    ├── src/pages/{NewAnalysis.tsx,RunView.tsx,History.tsx,Datasets.tsx}
    ├── src/components/{agent-timeline/,insights/,charts/,report/,quality/}
    ├── src/lib/{api-client.ts,ws.ts,types.gen.ts}
    └── tests/unit/
```

---

## 13. Implementation phases

**Deadline: Sunday 4 Oct 2026.** *Re-baselined on Saturday 3 Oct:* the Friday blocks didn't happen, so all the work now fits into Saturday and Sunday. **Build-first rule (agreed with you):** the first pass writes the code end to end, without stopping to test each piece. Tests are written and run together in block F. All keys and env vars start as `REPLACE_ME` placeholders.

| When | Block | Tasks (priority order) | Exit criterion |
|---|---|---|---|
| **Sat (you, in parallel)** | **Accounts** | AWS account setup (§11.1); sign up for Langfuse Cloud, Tavily, OpenAI and Gemini keys when convenient | `aws sts get-caller-identity` works |
| **Sat morning** | **A+B. Skeleton + data + analytics** | 1. Repo skeleton: backend (FastAPI, pip/`pyproject.toml`), frontend (Vite React TS), `docker-compose.yml` (postgres, gotenberg), `.env.example` with placeholders. 2. Adapters: SingStat MCP (+ REST fallback), Data.gov.sg (CSV), internal mock DB (SQL), MOM Excel; canonical format; snapshot fallback. 3. Quality checks + cleaning. 4. Analytics functions + `Fact` model + Plotly chart builders. 5. Web tools (search providers, safe fetch, extraction + grounding, trust tiers) | Code complete for the data layer |
| **Sat afternoon** | **C. LLM router + agents** | 1. `LLMRouter` (OpenAI, Gemini, scripted `MockLLM`, fallback, circuit breaker, cost). 2. LangGraph graph: Coordinator, ReAct Extraction + Analytics, Writer, deterministic Verifier + rewrite loop, clarification interrupt, re-planning. 3. Langfuse handler + masking + scores. 4. CLI runner | `python -m app.cli "…"` produces a report on `MockLLM` |
| **Sat evening** | **D. API + realtime** | 1. DB models + seed. 2. REST endpoints + `TaskRunner` + event bus → WebSocket + replay. 3. Export md/json/csv + PDF via Gotenberg. 4. Access-token middleware, rate limit | Run via REST, events over WS |
| **Sat night** | **E. Frontend core** | 1. Query page → run view with live timeline. 2. Insights, charts, report, data quality. 3. History. 4. Export buttons, clarification card | **Full demo flow in the browser** ← critical milestone |
| **Sun morning** | **F. First run + fixes + tests** | 1. `docker compose up` and fix what breaks. 2. Real keys in, if provided. 3. Core tests: analytics, verifier/hallucination, web safety, data quality, graph integration with mock, API. 4. Chaos toggles. 5. Locust run + coverage | Demo flow works; CI green |
| **Sun midday** | **E2. AWS** | Terraform → `plan` → **`apply` with your go-ahead** → push images → migrate → services up → check through CloudFront | Live on ECS |
| **Sun afternoon** | **G. Docs + CD + essay** | 1. README, ARCHITECTURE, DATA_SOURCES, TESTING, DEPLOYMENT. 2. INNOVATION.md. 3. `deploy-ecs.yml` (OIDC); final deploy through the pipeline. 4. Fresh-clone check. 5. `make aws-pause` | Submission-ready |

**Moved to stretch by the re-baseline:** Cloud Run files and docs, the self-hosted Langfuse compose file, frontend unit tests (Vitest), PDF export polish. PDF export is still built, but last in block D.

**Stretch, only if ahead of schedule:** arq + Redis worker, pgvector RAG (catalogue search and past reports), cross-provider LLM-as-judge, forecasting, Playwright E2E, security scans, `/datasets` page, a third LLM provider (Bedrock/Azure), a cost dashboard in the UI (cost is still logged per run in the MVP), Langfuse prompt management and datasets, a remote Terraform state backend, an actual Cloud Run deployment.

**If time runs short on AWS:** the order for dropping things is: Cloud Run docs → the OIDC pipeline (deploy with `make aws-deploy` from your machine instead, and document it) → CloudFront (HTTP on the ALB, with the access token still on). The Terraform-provisioned ECS deployment itself is kept.

**MVP cut line**, if Saturday slips: 2 real sources + mock internal DB; Coordinator, Extraction, Analytics and Writer, with only the deterministic Verifier; OpenAI + Gemini adapters + `MockLLM`; run page with timeline + charts + report; history; Markdown/JSON export (PDF last). Everything else is additive.

**Time protection rules:**
- If a government API fights back for more than 30 minutes, switch that source to snapshot-only and record the problem in DATA_SOURCES.md. The brief explicitly accepts workarounds.
- No new feature starts after Sunday 1 pm. From then on it is docs, bug fixes and rehearsal only.

---

## 14. Documentation deliverables

- **README.md:** overview, architecture diagram, quick start (`cp .env.example .env && docker compose up`), keyless mock mode, running tests (`make test`, `make load`), **sample queries**, tech choices + justification, screenshots.
- **ARCHITECTURE.md:** component diagram, LangGraph diagram, sequence diagram of a run (UI→API→TaskRunner→graph→event bus→WS), agent responsibilities and tool contracts, DB schema (ERD), LLM routing and fallback, error-handling matrix (§4.4), design decisions and trade-offs (ADR-style bullets), scalability notes.
- **TESTING.md:** strategy & pyramid, how to run each suite, **hallucination detection methodology** (§10.2), accuracy golden set, consistency results, data-quality cases, load-test results (p50/p95, RPS), coverage report.
- **DEPLOYMENT.md:** environment matrix (§11.3), local Compose, AWS ECS step by step (one-time setup, OIDC role, secrets, deploy workflow, migrations, rollback, teardown), the Cloud Run alternative, Langfuse setup (Cloud keys or self-hosted), and the single-replica constraint and how to scale out.
- **DATA_SOURCES.md:** each source's endpoints, auth, rate limits, datasets used (IDs, URLs, licences: Singapore Open Data Licence), format quirks found and how they were handled, sector harmonisation, the snapshot and fallback approach, and the mock internal DB design and generator.

### Sample queries to support and showcase
1. "Analyse employment trends in the technology sector from 2020–2024" (primary demo)
2. "Compare unemployment rates across sectors before and after COVID-19"
3. "Is there a correlation between ICT sector GDP growth and employment growth?"
4. "Which sectors had the highest retrenchments in 2023 and how does that compare to 2019?"
5. "How did the workforce training programme enrolments relate to placements in the tech sector?" (uses the internal DB)
5a. "Why did tech-sector retrenchments rise in 2023, and what did MOM say about it?" (**web search**: official SingStat retrenchment data for the numbers, plus MOM report pages and news for context, shown with trust tiers)
6. "Forecast technology sector employment for the next two years" (bonus)
7. Ambiguous: "How is the job market doing?" (shows clarification)

---

## 15. Live demo script (20 min)

| Time | Segment | What to show |
|---|---|---|
| 0–2 | Context | Problem, architecture slide (one diagram) |
| 2–9 | **End-to-end run** | Primary query: Coordinator intent + plan, parallel extraction from SingStat (**through DOS's official MCP server**: search → metadata → data), Data.gov.sg and MOM Excel, a web search step for context (with trust-tier badges), data-quality panel (issues found and fixed), analytics ReAct steps, charts, streamed report with hover-to-see-fact citations, verification badge, export PDF |
| 9–12 | **Failure handling** | Toggle chaos: SingStat down → snapshot fallback; OpenAI down → Gemini fallback (timeline + cost); ambiguous query → clarification card |
| 12–15 | Architecture & agents | LangGraph graph, ReAct sub-graph, Verifier loop, "LLM reasons, code computes", LLM router; **Langfuse trace of the run just shown** (nested spans, the fallback span, verifier scores); ECS deployment diagram |
| 15–17 | Testing | CI run, coverage, hallucination-injection test, consistency results, load-test numbers |
| 17–20 | Challenges & Q&A | Messy MOM Excel, sector harmonisation, API quirks, nondeterminism; production considerations |

**Backup:** a recorded video of the full run and `LLM_MODE=mock` + offline snapshots in case of network trouble.

---

## 16. Section 2: Innovation essay outline (`INNOVATION.md`, about 1–2 pages)

Each point is tied to a concrete element of the implementation:

1. **Trust & transparency:** extend the Fact/citation and Verifier system into a "show your working" view. Every number links to its tool call, code and raw source row, and confidence badges are calibrated against verification results. Researchers can export a reproducible notebook for each analysis.
2. **Agent adaptability:** a learned dataset-selection memory (which datasets answered which intents, ranked by researcher feedback); schema-drift detection, where adapters self-check against stored schemas and an agent proposes mapping fixes for human approval when an API changes; a self-healing source registry.
3. **Real-world data challenges:** explicit uncertainty propagation (provisional data, revisions, gaps); vintage tracking so a report shows which data release it used; and synthetic or differentially-private views for sensitive internal data.
4. **Security & compliance in government:**
   - deploy on government cloud (GCC 2.0) with private endpoints to LLMs (Bedrock/Azure in-region) and a data-classification-aware router (Restricted data → on-prem/open-weight model only);
   - PII redaction before LLM calls, and a full audit trail of every prompt, response, tool call and decision through **self-hosted Langfuse** inside the government boundary. This builds on the masking and trace scores already in the implementation (§4.3a);
   - RBAC/ABAC per dataset;
   - IM8 alignment;
   - prompt-injection defences for ingested content.
5. **Scalability:** push heavy aggregation down into the database or DuckDB/Parquet instead of pandas; horizontally scale workers; cache facts across runs; stream partial results.
6. **Collaboration:** shared workspaces, comment threads on insights, a team knowledge base (RAG over approved past reports), templated recurring briefs (e.g. a monthly labour market brief) run on a schedule, with diffs against last month.
7. **Multi-cloud resilience & cost:** cost- and latency-aware routing (cheap model for ReAct steps, strong model for synthesis), budget caps per run and team, semantic caching, provider health scoring, and evaluation-gated model upgrades using the golden set from §10.3.

---

## 17. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Government APIs change, rate-limit or are down during the demo | Snapshot fallback + offline mode; Phase 0 spike; recorded backup video |
| MOM Excel layouts are irregular | Per-file parser config (header rows, footnotes); fixture tests for each file |
| Sector definitions differ across sources | Curated `sector_map.yaml`; cross-source consistency check with flagged divergence |
| LLM nondeterminism makes tests flaky | MockLLM for CI; temperature 0; live LLM evals separate and nightly; tolerance-based assertions |
| LLM cost overrun | Cheap models for ReAct steps, caching, per-run budget cap, cost tracking |
| Scope creep vs deadline | Fixed time blocks, MVP cut line and stretch list (§13); feature freeze Sunday 1 pm |
| API keys arrive late or not at all | `LLM_MODE=auto` falls back to a scripted `MockLLM`; provider fallback is proven with fake providers in tests, so no real keys are needed to demonstrate it |
| ECS setup eats Sunday time | Infrastructure goes up early (block E2, Saturday) so surprises show up a day ahead; there is a fixed order for dropping AWS extras (§13); the demo always runs on local Compose |
| Surprise AWS bill on a personal account | Budget alerts set before any resource is created; no NAT gateway; small instance sizes; `make aws-pause` between sessions; `make aws-destroy` after evaluation; cost table in §11.1 |
| Public URL abused to burn LLM credits | `APP_ACCESS_TOKEN`, rate limiting, per-run budget cap, provider-side spending limits |
| Secrets leaking into Terraform state or git | RDS-managed master password; Terraform creates only the secret containers and values are set through the CLI; state file git-ignored; GitHub uses OIDC, not access keys |
| New-account delays (verification, service quotas) | Account set up Friday, in parallel with block A; checked with `aws sts get-caller-identity` before any Terraform work |
| In-process runner breaks when scaled to more than one replica | Pinned to 1 replica on ECS and Cloud Run, with the reason documented; the Redis + arq scale-out path is designed behind the `TaskRunner` interface |
| WebSocket drops behind the ALB or Cloud Run | ALB idle timeout set to 300s, server pings every 20s, client reconnect + event replay |
| Traces leak sensitive data to a third-party service | Langfuse masking function, configurable capture of prompt/response text, and self-hosting option; disabled unless keys are set |
| SingStat MCP changes or goes down (third-party dependency, `listChanged`) | REST Table Builder fallback using the same resource IDs, snapshot fallback, nightly contract test |
| Web content is wrong, hostile or used to attack the server | Trust tiers (Tier 3 = context only), deterministic grounding check, injection filter + no tools during extraction, SSRF guards incl. AWS metadata IPs, size/time limits |
| Tavily free tier (1,000 credits/month) runs out | Per-run search/fetch budget, response cache, DuckDuckGo keyless fallback, `mock` provider in CI |
| Real keys reveal prompt/format issues late | Real provider adapters are built against the same structured-output schemas the mock uses; a live smoke run is scheduled as soon as keys arrive (Sun morning at the latest) |

---

## 18. Decisions log

| # | Topic | Decision |
|---|---|---|
| 1 | Deadline | **Sunday 4 Oct 2026.** Schedule in §13 is compressed to about 2.5 days with an explicit stretch list. |
| 2 | LLM API keys | Provided later. `.env.example` uses `REPLACE_ME` placeholders and `LLM_MODE=auto` runs on `MockLLM` until real keys are set (§9). The plan still assumes OpenAI + Gemini. |
| 3 | Frontend | **React + TypeScript on Vite**, replacing Next.js. TypeScript is kept because the brief names it explicitly (§3, §7). |
| 4 | PDF export | **Gotenberg** instead of WeasyPrint. It renders Plotly charts with Chromium, and the backend image stays slim (§3). |
| 5 | Deployment target | **AWS ECS on Fargate, actually deployed to a personal AWS account** (`ap-southeast-1`), provisioned by Terraform and updated by a GitHub OIDC deploy pipeline. CloudFront provides HTTPS without a domain, and an access token protects the public URL. **Google Cloud Run is the documented alternative** (§11.1–11.3). The live demo runs on local Compose, with the ECS URL as proof of deployment. |
| 6 | Task processing | In-process asyncio `TaskRunner` instead of arq + Redis, to cut moving parts for the deadline. arq + Redis is documented as the scale-out path (§3). This pins the api service to 1 replica on ECS and Cloud Run. |
| 7 | Agent tracing | **Langfuse** through the LangGraph callback handler: one trace per analysis run, fallback metadata, verifier and quality scores, PII masking. Optional (no-op without keys). **Langfuse Cloud Hobby tier** for local and ECS; off in CI and load tests to stay within 50k units/month; self-hosting documented as the production path for government use (§4.3a). |
| 8 | HTTPS / domain | No custom domain, so **CloudFront in front of the ALB** provides HTTPS on `*.cloudfront.net` (§11.1). |
| 9 | SingStat access | **SingStat MCP as the primary access path** (verified live on 3 Oct 2026: 3 tools, no auth, streamable HTTP). Discovery and metadata tools go to the agent directly, and data fetches are wrapped by our adapter. REST Table Builder API and snapshots as fallbacks (§5.3). |
| 10 | Web search & extraction | **Added to the Extraction agent**: `web_search` / `fetch_web_page` / `extract_web_data` with Tavily (free tier) → DuckDuckGo → mock, trust tiers, grounding check, SSRF and injection guards, per-run budget (§5.4). |
| 11 | Build-time simplifications (3 Oct) | Plain pandas quality checks instead of pandera (every rule explicit and testable); Tailwind components instead of shadcn/ui; official `mcp` SDK client directly instead of `langchain-mcp-adapters` (discovery/metadata tools still exposed to the agent as tools); `create_all` + seed (`python -m app.db.init`, also the ECS migration task) instead of Alembic; pip instead of uv. Installed versions: mcp 2.3, langgraph 1.2, langchain-core 1.6, langfuse 4.16. |
| 12 | ReAct implementation | Provider-neutral structured `ReActStep` JSON (thought / action / input / final answer) inside LangGraph nodes, so OpenAI, Gemini and the scripted MockLLM behave identically and the thought is explicit for the timeline. |
| 13 | Access token header | The frontend sends `X-Access-Token`, not `Authorization`, because CloudFront only forwards `Authorization` when it is part of the cache key. |
| 14 | LLM providers (7 Oct) | **OpenAI + Google Gemini** stay the two providers (Anthropic was considered and dropped as the least-effort option). `LLM_PROVIDER_ORDER` also accepts `google` as an alias for `gemini`. |
| 15 | Source resilience (7 Oct) | The SingStat MCP (behind CloudFront) rate-limits bursts with 403s. Per-transport **circuit breakers** (2 failures or any 403/429 → skip for 2 min); chaos errors are not retried and never trip the real breaker. A fallback response **never overwrites a primary (MCP) snapshot**. REST fallback search goes keyword by keyword and ranks level tables above "changes" tables. |
| 16 | Data.gov.sg search (7 Oct) | The v2 API ignores `query`. A **local catalogue index** (`data/datagov_catalogue.json`, built by `python -m app.scripts.build_datagov_index`, 4,643 datasets) is searched by keyword; the live API is the fallback when the index is missing. |
| 17 | Verifier (7 Oct) | Added: a named sector must be what the cited facts measure (found by the mutation evaluation: 0/8 caught before); comma-grouped numbers are never years. Evaluation: 150/150 injected hallucinations caught, 0/29 false positives (TESTING.md). |
| 18 | Sub-annual data (7 Oct) | New deterministic `annualise` analytics tool: complete years only, sum for flows, mean for levels, registered as a derived dataset `<key>~annual` so citations stay valid. |
| 19 | Cost and admin safety (7 Oct) | `RUN_LLM_BUDGET_USD` is enforced by the router (rest of the run on MockLLM, reported once). `PUT /admin/chaos` is allowed only for `APP_ENV` local/dev/test/ci unless `CHAOS_ADMIN_ENABLED=true`. |
| 20 | Frontend bundle (7 Oct) | Plotly lazy-loaded and switched to the `plotly.js-basic-dist-min` bundle (scatter/bar only): app shell 397 kB, chart chunk 380 kB gzipped instead of 1.4 MB. |
| 21 | GitHub OIDC trust (7 Oct) | The deploy role trusts `repo:<owner>/<repo>:environment:aws`, because jobs in the `aws` environment get that subject rather than `:ref:`. |

### Still open
- AWS deployment (steps in DEPLOYMENT.md) waits on working AWS credentials. Live-LLM runs wait on a `GOOGLE_API_KEY` (OpenAI is available from the system environment). Langfuse and Tavily keys are optional.
