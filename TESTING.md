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
| Evaluation: hallucination detection | 150 injected hallucinations across 4 sample queries (section 3) | `tests/eval/test_hallucination_eval.py` | 1 |
| Load | Locust, 50 users for 2 minutes against the Docker stack | `tests/load/locustfile.py` | (section 6) |
| Frontend | ESLint, `tsc` type check, production build; the full flow checked in a browser | CI `frontend` job | |
| End to end | Docker Compose stack started in CI, one analysis run to completion | CI `smoke` job | |

## 2. How to run

```bash
cd backend
.venv/Scripts/pytest -m "not contract and not llm" --cov=app --cov-report=term --cov-report=html
.venv/Scripts/pytest tests/integration                      # one level
.venv/Scripts/pytest tests/unit/test_verifier.py::test_injected_wrong_number_fails
.venv/Scripts/pytest tests/eval -s                          # prints the evaluation table
.venv/Scripts/ruff check app tests

cd frontend && npm run lint && npm run typecheck && npm run build

make load-stack   # restart the api offline, on MockLLM, tracing off, rate limit raised
make load         # Locust headless: 50 users, ramp 10/s, 2 minutes
```

The markers `contract` (live external services) and `llm` (live providers, costs money) are opt-in and
excluded from CI.

**CI** (`.github/workflows/ci.yml`) runs on every push and pull request:

1. backend: ruff, then pytest with coverage (XML and HTML report uploaded as an artefact);
2. frontend: ESLint, type check and build;
3. smoke: `docker compose up --build` with MockLLM and offline snapshots, then one analysis via the API
   must reach `completed`;
4. images: on `main`, push the backend and frontend images to GHCR.

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

Run: `make load-stack && make load`. That is the Docker Compose stack on a Windows 11 laptop (Docker
Desktop), API offline on MockLLM with tracing off, 50 users ramping at 10 per second for 2 minutes, and
1-3 s think time per user.

| Endpoint | Requests | Failures | Median | p95 | p99 |
|---|---|---|---|---|---|
| GET /analyses (history) | 1,286 | 0 | 10 ms | 63 ms | 110 ms |
| GET /analyses/{id} | 808 | 0 | 5 ms | 22 ms | 100 ms |
| GET /analyses/{id}/events | 416 | 0 | 12 ms | 35 ms | 100 ms |
| GET /readyz | 183 | 0 | 13 ms | 46 ms | 140 ms |
| POST /analyses (starts a run) | 211 | 0 | 52 ms | 66 ms | 100 ms |
| **All** | **2,904** | **0** | **10 ms** | **58 ms** | **110 ms** |

Throughput was 24.4 requests/s, bounded by the users' think time rather than the server. All 211
analyses started during the test **completed**, while the API stayed at about 210 MiB. Finished runs
beyond the last 25 are evicted from memory, so it doesn't grow with history. The offline/mock setup
measures the platform rather than LLM latency, and avoids hammering government APIs.

## 7. Coverage

Backend line coverage: **82%** (3,363 statements, 143 tests, about 40 s). Highlights:

| Module | Coverage |
|---|---|
| `agents/graph.py` | 97% |
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
- Exports: Markdown, JSON, CSV (zip) and PDF (Gotenberg, about 4.5 s).
- Failure scenarios against the running stack: MCP down → REST; MCP and REST down → snapshots;
  Data.gov.sg down → snapshot; injected hallucination → rewrite. A real MCP rate-limit block (403 from
  CloudFront) led to the per-transport circuit breaker.

## 9. Not yet covered

- Live-provider evaluation (`-m llm`): run the golden queries on OpenAI and Gemini and compare
  intents, plans and verification rates. It needs keys and costs money, so it is not in CI.
- Contract test against the live SingStat MCP `tools/list` (`-m contract`), intended as a nightly job.
- Frontend unit tests (Vitest) and browser E2E (Playwright). The CI smoke job covers the API path
  end to end.
