# Testing

## 1. Strategy

The design makes most of the system deterministic, so most of it can be tested exactly:

- **Numbers come from code, not the model.** Statistics are pure functions tested against hand-computed
  values, and a report can only contain numbers from those functions.
- **The model is replaceable in tests.** A scripted MockLLM drives the real graph, tools and checks;
  only the LLM's choices are scripted. Tests never call a paid API: `conftest.py` forces placeholder
  keys even when real keys are in the developer's environment.
- **The data is replayable.** Recorded source snapshots make end-to-end runs deterministic and offline.

| Level | What | Where | Tests |
|---|---|---|---|
| Unit: analytics | describe, change, CAGR, YoY, OLS trend, share, Pearson/Spearman, anomalies, forecast, annualise, against hand-computed values | `tests/unit/test_stats.py` | 21 |
| Unit: verifier | Correct claims pass; injected numbers, uncited numbers, missing facts/sources, out-of-range years, unknown sectors and wrong-sector claims fail; rounding tolerance; "1,910" is not a year | `tests/unit/test_verifier.py` | 13 |
| Unit: web safety | SSRF (schemes, metadata hosts, hosts resolving to private IPs), prompt-injection detection and stripping, grounding, trust tiers, decoding, table and link extraction | `tests/unit/test_web_safety.py` | 28 |
| Unit: data quality | Duplicates, isolated-gap interpolation vs runs never invented, missing-value severity, negative counts, impossible percentages, missing years, hierarchy mismatch, fallback provenance | `tests/unit/test_quality.py` | 9 |
| Unit: LLM router | Mock/auto chains, primary healthy, fallback with event and log, mock last resort, live mode raising, circuit breaker, chaos outage, budget cap, cost accounting | `tests/unit/test_llm_router.py` | 11 |
| Unit: sources | Period parsing, snapshots, SingStat MCP → REST → snapshot fallback, snapshot protection, circuit breakers, REST search ranking, Data.gov.sg catalogue search, offline replay | `tests/unit/test_sources.py` | 20 |
| Unit: config | Placeholder detection, provider and env-var aliases, whitespace, chaos-admin gating, DB URL composition | `tests/unit/test_config.py` | 21 |
| Integration: multi-agent workflows | Full graph through the real task runner: main query, every claim traced to a fact, consistency, injected hallucination → rewrite, clarification → resume, correlation on internal data, forecast labelling, all sources down → snapshots, quarterly data annualised, clarified metric is the one analysed | `tests/integration/test_graph.py` | 10 |
| API | Health and readiness, create → poll → export (md/json/csv), event replay with `after`, validation and 404, clarify conflicts, chaos toggles locally and refused on AWS, access token, provider status | `tests/api/test_api.py` | 9 |
| API: chats | Chat titles, follow-ups that inherit context and reuse downloaded data, turns and versions, retry keeps the old answer, one question at a time, pin/rename/search/delete, legacy runs as one-question chats, provider preference, follow-up suggestions, run summary | `tests/api/test_chats.py` | 12 |
| API: run activity | Week/month/year boundaries, the viewer's time zone (unknown zones fall back to UTC), status counts and running totals, no periods before the first run | `tests/api/test_activity.py` | 7 |
| WebSocket | Replay ends with a `replay_done` marker after the last stored event | `tests/api/test_ws.py` | 1 |
| Export: Word | Every number in the .docx matches the Markdown export | `tests/unit/test_docx_export.py` | 1 |
| Evaluation: hallucination detection | 150 injected hallucinations across 4 sample queries (section 3) | `tests/eval/test_hallucination_eval.py` | 1 |
| Load | Locust, 50 users for 2 minutes against the Docker stack | `tests/load/locustfile.py` | (section 6) |
| Frontend (Vitest + Testing Library) | Sidebar grouping, rename and confirmed delete; chat bar; answer versions and retry; clarification focus; Radix wrappers (tabs keyboard navigation, dialogs, switch, menus, progress, toasts); plain-language activity sentences on recorded runs; evidence underline; stage progress; replay watermark; Run activity page | `frontend/src/**/*.test.ts(x)` | 41 |
| Frontend: static | ESLint, `tsc` type check, production build; the full flow checked in a browser | CI `frontend` job | |
| End to end | Docker Compose stack started in CI; a chat's first question and a follow-up both run to completion through `/chats` | CI `smoke` job | |

## 2. How to run

The backend environment comes from `backend/uv.lock` (`uv sync`, or `make install`); `uv run` works the
same on Windows, macOS and Linux.

```bash
cd backend
uv run pytest -m "not contract and not llm" --cov=app --cov-report=term --cov-report=html
uv run pytest tests/integration                             # one level
uv run pytest tests/unit/test_verifier.py::test_injected_wrong_number_fails
uv run pytest tests/eval -s                                 # prints the evaluation table
uv run ruff check app tests

cd frontend && npm run lint && npm run typecheck && npm test && npm run build

make load-stack   # restart the api offline, on MockLLM, tracing off, rate limit raised
make load         # Locust headless: 50 users, ramp 10/s, 2 minutes
```

The markers `contract` (live external services) and `llm` (live providers, costs money) are opt-in and
excluded from CI.

**CI** (`.github/workflows/ci.yml`) runs on every push and pull request:

1. backend: `uv sync --locked` (fails if `uv.lock` is out of date with `pyproject.toml`), ruff, then pytest
   with coverage (XML and HTML report uploaded as an artefact);
2. frontend: ESLint, Vitest, type check and build;
3. smoke: `docker compose up --build` with MockLLM and offline snapshots, then a chat is started via
   `POST /chats`, a follow-up is sent to `/chats/{id}/messages`, and both runs must reach `completed`;
4. images: on `main`, push the backend and frontend images to GHCR.

A separate monthly workflow scans dependencies and images for known vulnerabilities (section 9).

## 3. Hallucination detection

### Method

Hallucination control is built into the pipeline, not bolted on. Each layer below is tested.

1. **Grounded generation.** The writer only receives Facts: numbered results of deterministic
   computations, each with a value, display text, method and source keys. It must return claims with
   `fact_ids` and `source_keys`.
2. **Numeric verification.** Every number in a claim is extracted (signs, percentages, thousands
   separators) and must match a *cited* Fact within the precision it is written in: "14.4%" matches
   14.4035, "14.6%" does not. Percent and absolute forms are both accepted. Comma-grouped counts are
   never treated as years.
3. **Citation integrity.** Cited fact ids and source keys must exist in the run. Source keys missing from
   a claim are back-filled from its facts, so every published claim carries citations.
4. **Entity grounding.** Years must fall inside the collected data (plus a 3-year projection horizon),
   and named sectors must exist in the data. A named sector must also be **what the cited facts
   measure**, which catches "Construction grew 14.4%" when 14.4% is the ICT figure.
5. **Rewrite, then drop.** Failing claims go back to the writer with the reasons, at most twice. Anything
   still failing is removed, and the report says how many claims were removed.
6. **Web content.** Tier-3 sources are context only; numbers extracted from a page must literally
   appear in it; injection phrases are flagged and stripped; page text is fenced as untrusted.

### Results

**Mutation evaluation** (`tests/eval/test_hallucination_eval.py`). Four sample queries run end to end.
Every claim in their verified reports is a known-good claim. Each claim is then mutated in seven ways
that model real LLM failure modes, and the verifier must flag every mutation and none of the originals.

| Hallucination injected | Mutated claims | Flagged | Recall |
|---|---|---|---|
| perturbed number (+10%) | 25 | 25 | 100% |
| fabricated extra sentence ("rose by 37.5%") | 29 | 29 | 100% |
| year outside the data | 13 | 13 | 100% |
| right numbers, wrong sector | 8 | 8 | 100% |
| citation to a missing fact | 29 | 29 | 100% |
| numeric claim, citations removed | 25 | 25 | 100% |
| cites an unrelated fact | 21 | 21 | 100% |
| **All** | **150** | **150** | **100%** |

Unmodified claims: 29, wrongly flagged: 0 (precision 100%).

The evaluation found a real gap. The first version of the verifier caught **0 of 8** wrong-sector
mutations (95% overall), because the numbers matched the cited facts and the swapped-in sector existed
elsewhere in the collected tables. The sector-to-fact consistency check (layer 4) closed it, and the
test above guards it.

**Live rewrite loop.** With *inject a hallucination* on, draft 1 is rejected
(`number 37.5% not supported by any fact`, `... by the cited facts`), draft 2 passes, and 37.5% never
reaches the report (`test_injected_hallucination_is_caught_and_rewritten`).

**False positives found by running real queries.** The retrenchment query originally lost 2 true claims
because "1,910" retrenchments was read as the year 1910. The year check now ignores comma-grouped
numbers, with a regression test.

Limits of this approach: the checks are lexical. They catch wrong numbers, citations, years and
subjects, but not a claim whose numbers are right while its *interpretation* is wrong (e.g. calling a
fall "growth"). The next layer is a cross-provider LLM judge scoring each claim's faithfulness to its
cited facts, with a different provider from the writer. It is designed for (`TASK_TIERS["judge"]`), not
built.

## 4. Accuracy and consistency

- **Hand-computed checks.** Analytics functions are tested on series with known answers: +10% a year
  gives CAGR 10.0% and slope 11.03 (worked in the test), an exact line forecasts exactly with a
  zero-width interval, a linear transform correlates at 1.0, quarterly 1+2+3+4 annualises to 10, and an
  incomplete year is dropped.
- **Against the source.** For the main query the report states ICT employment of 157.6 thousand (2020)
  and 180.3 thousand (2024), the values in SingStat M182841. By hand: (180.3 − 157.6) / 157.6 = 14.40%
  and (180.3 / 157.6)^(1/4) − 1 = 3.42%. The report shows 14.4% and 3.4%.
- **Consistency.** The same query run twice produces identical fact sets (keys and values),
  `test_same_query_twice_gives_identical_facts`. Numbers can't drift between runs because they come from
  tools, not text generation. With a live LLM, the wording and the choice of analyses can vary, but
  every number still passes the same verifier.
- **Every sample query** completes with 100% numeric, citation and entity pass rates, both online and in
  offline mode.

## 5. Data quality

`tests/unit/test_quality.py` uses fixtures with deliberate defects. Each defect must be detected and
handled as designed:

| Defect | Detection | Handling |
|---|---|---|
| Duplicate series/period rows | consistency warning | De-duplicated; action recorded |
| Single missing value inside a series | completeness warning | Linear interpolation, recorded |
| Two or more consecutive missing values | completeness | Excluded, never invented |
| > 20% missing | completeness **error** | Score penalised |
| Negative counts, percentages outside [-100, 100] | validity **error** | Score penalised (0.75) |
| Requested years absent | timeliness | Listed in the report |
| Parent ≠ sum of children beyond rounding | consistency info | Explained (source lists selected sub-sectors) |
| Served from a fallback | provenance warning | Shown on the dataset and in Limitations |

Integration tests check the same pipeline on real snapshot data, and the UI's *Data & quality* tab shows
every report and action.

## 6. Performance and load

Run: `make load-stack && make load`. That is the Docker Compose stack on a Mac laptop (Docker Desktop,
re-run 20 Oct), API offline on MockLLM with tracing off, 50 users ramping at 10 per second for 2 minutes,
and 1-3 s think time per user. The traffic follows the chat app: list chats, open a chat, start a chat and
send follow-ups, plus the per-run reads (detail, event replay). A follow-up that gets 409 (the chat's
previous question is still running) is expected under load and counted as a success.

| Endpoint | Requests | Failures | Median | p95 | p99 |
|---|---|---|---|---|---|
| GET /chats | 956 | 0 | 15 ms | 44 ms | 71 ms |
| GET /chats/{id} | 807 | 0 | 4 ms | 24 ms | 46 ms |
| GET /analyses/{id} | 359 | 0 | 4 ms | 16 ms | 35 ms |
| GET /analyses/{id}/events | 292 | 0 | 8 ms | 30 ms | 52 ms |
| GET /readyz | 158 | 0 | 9 ms | 32 ms | 43 ms |
| POST /chats (starts a run) | 177 | 0 | 5 ms | 25 ms | 51 ms |
| POST /chats/{id}/messages (follow-up) | 161 | 0 | 9 ms | 35 ms | 62 ms |
| **All** | **2,910** | **0** | **9 ms** | **35 ms** | **57 ms** |

Throughput was 24.6 requests/s, bounded by the users' think time rather than the server. `GET /chats` is
the slowest read because it queries each chat's runs one chat at a time. Not re-measured in this run:
whether every started run completed, and the API's memory use (7 Oct: all 211 runs completed, about
210 MiB; finished runs beyond the last 25 are evicted from memory, so it doesn't grow with history). The
offline/mock setup measures the platform rather than LLM latency, and avoids hammering government APIs.
The earlier 7 Oct run (2,904 requests, 0 failures, p95 58 ms) used the legacy `/analyses` endpoints and a
different request mix, so the two are not directly comparable.

## 7. Coverage

Backend line coverage: **83%** (3,876 statements, 164 tests, about a minute; measured 19 Oct). Highlights:

| Module | Coverage |
|---|---|
| `agents/graph.py` | 98% |
| `llm/router.py` | 96% |
| `quality/checks.py` | 95% |
| `verification/checks.py` | 95% |
| `analytics/stats.py` | 93% |
| `web/fetch.py` | 84% |

Lower coverage is in code that needs live services or a browser: live LLM provider adapters, the
Langfuse integration, the WebSocket handler (exercised in the browser and the CI smoke run), and the
one-off scripts. The HTML report is uploaded by CI as the `backend-coverage` artefact.

## 8. Manual checks done

- Full stack via `docker compose up --build`: all services healthy, `/readyz` reports database and
  Gotenberg OK.
- Browser walk-through: sample question → live timeline over WebSocket → insights with fact citations →
  charts → data & quality → report → plan → history; clarification card → resume; demo toggles.
- Chat layout (14-15 Oct, MockLLM, offline, DOM-level checks): Home, sidebar, a follow-up question
  answered with its own facts, the Preview panel, the activity dialog, run details and Run activity, plus
  a 390 px viewport (drawer and preview sheet, no sideways scroll).
- Exports: Markdown, JSON, CSV (zip) and PDF (Gotenberg, about 4.5 s).
- Failure scenarios against the running stack: MCP down → REST; MCP and REST down → snapshots;
  Data.gov.sg down → snapshot; injected hallucination → rewrite. A real MCP rate-limit block (403 from
  CloudFront) led to the per-transport circuit breaker.

## 9. Security scanning (CVEs)

`.github/workflows/security.yml` runs at 02:00 UTC on the 1st of every month, and on demand from the
Actions tab:

| Job | Tool | Scans | Fails on |
|---|---|---|---|
| python | `pip-audit` | runtime packages pinned in `backend/uv.lock` (exported with hashes) | any known vulnerability |
| node | `npm audit` | `frontend/package-lock.json`, dev tooling included | high or critical |
| images | Trivy | the built backend and frontend images: OS packages and installed Python packages | high or critical with a fix available |

Findings appear in the run summary. GitHub emails a failed scheduled run to whoever last changed the
workflow's cron line. The same checks run locally:

```bash
cd backend && uv export --locked --no-dev --no-emit-project -o req.txt && uvx pip-audit -r req.txt --disable-pip
cd frontend && npm audit --audit-level=high
```

First local run (19 Oct, same tools and versions as the workflow):

| Scan | Result |
|---|---|
| pip-audit, `uv.lock` runtime packages | no known vulnerabilities |
| Trivy, backend image (Debian 13 + `/opt/venv`) | 0 high or critical |
| Trivy, frontend image | **55 fixable (2 critical, 53 high)**, all in the `nginx:1.27-alpine` base (Alpine 3.21.3): OpenSSL, curl, expat, libpng, libxml2, musl, zlib and others. **Fixed the same day:** `nginx:1.30-alpine` (Alpine 3.24) plus `apk upgrade` in the Dockerfile → 0 |
| npm audit | 2 critical, 1 high, 5 moderate. The critical and high ones are dev tooling (vitest and its tinypool dependency, vite); the shipped bundle only had a moderate react-router advisory. **Fixed the same day:** vite 7.3.7, vitest 4.1.12, @vitejs/plugin-react 5.2, react-router-dom 7.18.4 → 0 vulnerabilities |

After the fixes, every job of the scan passes locally.

## 10. Not yet covered

- Live-provider evaluation (`-m llm`): run the golden queries on OpenAI and Gemini and compare
  intents, plans and verification rates. It needs keys and costs money, so it is not in CI.
- Contract test against the live SingStat MCP `tools/list` (`-m contract`), intended as a nightly job.
- Browser E2E (Playwright). The CI smoke job covers the chat API path end to end, and Vitest covers the
  components.
