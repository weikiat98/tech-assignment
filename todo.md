# TODO: open items

Snapshot: **Wednesday 7 Oct 2026**. The deadline no longer applies. LLM providers stay **OpenAI + Google
Gemini** (decision 14).

**Owner:** 👤 **You** = manual step only you can do · 🤖 **Claude** = I can do it when you say go ·
👥 **Both** = I prepare, you review or approve.

## Done on 7 Oct (verified)

- **Compose stack** (C3): `docker compose up --build` runs postgres, gotenberg, migrate, api and frontend;
  all healthy, `/readyz` OK.
- **Browser walk-through** (C4): query → live timeline → insights, charts, data & quality, report, plan →
  history; clarification card → resume; demo toggles. Fixed: the Charts tab snapped back to Insights on
  every click.
- **Exports**: md, json, csv (zip), html, PDF via Gotenberg (H8).
- **Scenarios against the stack** (H4-H7): web/"why" query, clarification, MCP down → REST, MCP + REST
  down → snapshot, Data.gov.sg down, injected hallucination → rewrite. Fixed along the way: quarterly
  data unusable (new `annualise` tool), event-year window ("rise in 2023" now includes 2020-2022),
  retrenchment wording, the clarified metric not being the one analysed, a "1,910 = year 1910" verifier
  false positive, fallback snapshots overwriting MCP recordings.
- **SingStat MCP rate-limiting** found live (CloudFront 403): per-transport circuit breakers, REST search
  fallback rewritten (keyword ranking).
- **Data.gov.sg search** (M2): the v2 API ignores `query`; replaced by a local catalogue index of 4,643
  datasets.
- **H9**: extraction prompt now requires every plan task; `fetch_datagov` fills a missing title from
  search results. *Not yet re-checked with a live LLM.*
- **H10**: correlation is demonstrated by sample query 4 (r = 0.89, n = 6).
- **H11** per-run LLM budget enforced; **H12** chaos admin disabled unless `APP_ENV` is
  local/dev/test/ci.
- **C5 / H22 / H24 / M5**: 143 tests, 82% backend coverage, ruff and ESLint clean, type check clean;
  hallucination evaluation 150/150 caught, 0 false positives (it found and closed a wrong-sector gap).
- **H23** load test: 50 users for 2 min, 2,904 requests, 0 failures, p95 58 ms, 211 runs completed.
- **M4** snapshots recorded for every sample query; all pass offline. **M6** runner keeps the last 25
  finished runs in memory. **M8** plan.md §3 brought in line with the code. **M11** Plotly lazy-loaded
  (basic bundle).
- **C6 docs**: README, ARCHITECTURE, TESTING, DATA_SOURCES, DEPLOYMENT written. **C7**: INNOVATION.md
  drafted.
- **Infra**: `terraform fmt` + `validate` pass. Fixed: the GitHub OIDC trust didn't allow the `aws`
  environment the deploy workflow uses; `deploy.sh` broke on Windows (`/tmp` vs `file://`).
- `.env` fixes: `LLM_PROVIDER_ORDER=openai,google` (now an accepted alias), `OPENAI_MODE` /
  `GOOGLE_MODEL` renamed to the real settings, `LANGFUSE_BASE_URL` now accepted, values whitespace-stripped.

## 🔴 Needs you

| # | Item | Details |
|---|---|---|
| A1 | ~~Fix AWS credentials~~ ✅ | Works with the SSO profile `meow98` (AdministratorAccess, `ap-southeast-1`): run `export AWS_PROFILE=meow98` before any `make aws-*`. The **default** profile holds a stale, invalid access key; delete it from `~/.aws/credentials` (or leave it unused) so nothing picks it up by accident. |
| A2 | **Google Gemini key** 👤 | `GOOGLE_API_KEY` in `.env` is still a placeholder, so the second provider has never been called. With it I can test Gemini directly and the OpenAI → Gemini fallback. |
| A3 | **Review and edit docs** 👤 | Especially INNOVATION.md (written in your voice as a draft; remove the comment on line 1). |
| A4 | **Commit and push** 👥 | Nothing from 7 Oct is committed yet. Say the word and I'll commit in logical chunks and push to `origin/main`. CI then runs on GitHub for the first time. |
| A5 | **Repo visibility** 👤 | Public, or invite the assessors. |
| A6 | Demo rehearsal + backup recording (C8) 👤 | plan.md §15. Keep `OFFLINE_MODE=true` + `LLM_MODE=mock` as the fallback. |

## 🟠 AWS deployment (after A1), steps in DEPLOYMENT.md §3

| # | Item | Owner |
|---|---|---|
| D1 | Fill `infra/terraform/aws/terraform.tfvars` (repo, email, budget, `langfuse_host`) | 👤 |
| D2 | `make aws-plan`; review the output | 👥 (I can run it once A1 works) |
| D3 | `make aws-apply` (billable, about US$3-4/day) | 👤 approve |
| D4 | Put real secrets into Secrets Manager, incl. a real `APP_ACCESS_TOKEN` | 👤 |
| D5 | `make aws-deploy`, then check token screen, WebSocket, PDF, `/readyz` via CloudFront | 👥 |
| D6 | GitHub: environment `aws` (main + `v*` only), secret `AWS_DEPLOY_ROLE_ARN`, 8 variables; run the workflow once | 👤 |
| D7 | `make aws-pause` until the demo; `make aws-destroy` after evaluation | 👤 |

## 🟡 With keys / nice to have

| # | Item | Owner |
|---|---|---|
| K1 | Live-LLM run of every sample query (OpenAI, then Gemini): agent quality (H9), out-of-scope handling (M10), verification rates | 🤖 (costs a few US cents per run) |
| K2 | Langfuse: traces appear, LLM calls nest under the run, scores attach, masking works, "Open trace" link | 🤖 after keys |
| K3 | Tavily / DuckDuckGo live search (only mock search has run) | 🤖 |
| K4 | Confirm model ids and prices in `llm/costs.py` (M3) | 👤 |
| M1 | MOM workbook is a disclosed sample built from MOM-sourced figures; optionally point `MOM_EXCEL_URL` at a real MOM download | 👤 decide |
| M7 | One DB session per event: fine at 50 users; batch if needed | 🤖 |
| M12 | Mobile layout, long-claim wrapping, empty states | 🤖 |

## 🟢 Stretch

L1 frontend unit tests (Vitest) · L2 Playwright E2E · L4 cross-provider LLM judge · L5 pgvector RAG ·
L6 arq + Redis worker · L7 self-hosted Langfuse compose · L8 nightly live-LLM eval and MCP contract
test · L9 security scans (pip-audit, npm audit, Trivy, gitleaks) · L10 Terraform remote state ·
L11 `/datasets` page and cost dashboard · L12 Alembic · Cloud Run files (documented in DEPLOYMENT.md §5).
