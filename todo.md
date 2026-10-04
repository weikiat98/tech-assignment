# TODO: open items before submission

Snapshot: **Sunday 4 Oct 2026** (deadline day). The first build pass is complete (plan.md §13 blocks A–E plus the infra files). Everything below is **not done, not run, not verified, or needs a manual action from you**.

**Owner:**
- 👤 **You** = a manual step only you can do (accounts, keys, approvals, GitHub settings).
- 🤖 **Claude** = I can do it when you say go.
- 👥 **Both** = I prepare it, you review or approve it.

**Verified so far (for context):**
- Backend imports cleanly.
- Frontend typechecks and builds (`tsc` + `vite build`).
- The CLI ran the main demo query end to end twice, with the verifier passing 100% both times:
  - once with a real LLM (your system `OPENAI_API_KEY`, gpt-4.1, about US$0.03);
  - once with the scripted MockLLM, using SingStat MCP ×2, the MOM Excel sample and a Data.gov.sg CSV.
- Snapshots for that query are recorded, so it also works offline.

Nothing else has been run.

---

## 🔴 Critical: blocks submission or the live demo

| # | Item | Owner | Details / how to close |
|---|---|---|---|
| C1 | **Create a GitHub repository and put the code in git** | 👤 You + 🤖 | The brief requires a GitHub repo. The folder is not a git repository yet. You create the empty repo on GitHub (public or private, as the assessors need). I then run `git init`, check `.gitignore` (no `.env`, `.venv`, `node_modules`, `*.tfstate`), commit and push, with your permission. |
| C2 | **Create `.env` from `.env.example`** | 👤 You | `cp .env.example .env`, then at least change `POSTGRES_PASSWORD`. ⚠ Your **Windows system environment has `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` set**, and the app reads system env vars automatically. Either keep it (live OpenAI, costs money) or put `LLM_MODE=mock` in `.env` while developing. |
| C3 | **`docker compose up` has never been run** | 🤖 Claude | Build all images and start postgres, gotenberg, migrate, api and frontend. Fix whatever breaks: Dockerfiles, the nginx template under a non-root user, healthchecks, the compose `depends_on` chain. |
| C4 | **The frontend has never been opened in a browser** | 🤖 Claude | Walk the full demo flow: new analysis → live timeline over WebSocket → insights with fact hover, charts, data quality, report, plan → history → each export button. |
| C5 | **No test suite exists, so CI will fail** | 🤖 Claude | `backend/tests/` only has the Locust file. The CI step `pytest` (no tests collected = exit code 5) fails, and `ruff check app tests` has never been run. Minimum set: analytics functions against hand-computed values, verifier (including an injected wrong number), web safety (SSRF / injection / grounding / trust tiers), quality checks on defect fixtures, LLM router fallback + circuit breaker, an API smoke test, and a graph integration run on MockLLM + offline snapshots. |
| C6 | **Required docs not written** | 🤖 Claude → 👤 review | The brief requires `README.md` (overview, setup, run, tests, sample queries, tech choices), `ARCHITECTURE.md`, `TESTING.md` (incl. hallucination method + results) and `DATA_SOURCES.md`. `DEPLOYMENT.md` is also planned. None exist yet. |
| C7 | **Section 2 essay `INNOVATION.md` not written** | 🤖 draft → 👤 edit | 1–2 pages, outline in plan.md §16. It should sound like you, so please edit my draft. |
| C8 | **Demo rehearsal and backup recording** | 👤 You | Follow plan.md §15. Record a backup video of a full run in case of network trouble. Keep `OFFLINE_MODE=true` + `LLM_MODE=mock` ready as the fallback. |

## 🟠 High: required by the brief, or a real risk

### Keys and accounts (all currently `REPLACE_ME` placeholders)

| # | Item | Owner | Details |
|---|---|---|---|
| H1 | **Google Gemini API key** | 👤 You | The brief requires **≥2 LLM providers**. Only OpenAI has been verified live, and the Gemini adapter has never been called. Put the key in `GOOGLE_API_KEY`, then I will test Gemini directly and the OpenAI→Gemini fallback (chaos toggle "OpenAI down"). |
| H2 | **Langfuse Cloud keys (Hobby tier, EU or US region)** | 👤 You | `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`. The tracing code targets **Langfuse SDK v4** (`start_as_current_observation`, `propagate_attributes`, `create_score`) and has **never run against a live project**. After that I need to check: traces appear, LLM calls nest under the run, verifier scores attach, masking works, and the "Open trace" link works. |
| H3 | **Tavily API key** (optional) | 👤 You | `TAVILY_API_KEY`. Without it, web search falls back to DuckDuckGo, which has also never been run. |

### Features built but never run

| # | Item | Owner | Details |
|---|---|---|---|
| H4 | **Web search + extraction path** | 🤖 Claude | `web_search` → `fetch_web_page` → `extract_web_data`, with SSRF guard, injection filter, grounding check and trust tiers. Run sample query 3 (the "why…retrenchments" query) and a run with "Include web context" on. |
| H5 | **Clarification interrupt / resume** | 🤖 Claude | Sample query "How is the job market doing?" → `awaiting_input` → answer in the UI → the run resumes. Uses LangGraph `interrupt` + `MemorySaver`. |
| H6 | **Failure handling (chaos toggles)** | 🤖 Claude | (a) SingStat MCP down → **REST fallback**. The REST endpoints answer, but **their payload shape is only assumed** to match the MCP's (`Data.row[].columns[]`), and search/metadata parsing is unverified. (b) Both down → snapshot. (c) Data.gov.sg down. (d) OpenAI down → Gemini (needs H1). |
| H7 | **Verifier rewrite loop** | 🤖 Claude | Toggle "inject hallucination" → draft 1 fails → rewrite → passes. Never exercised. |
| H8 | **PDF export through Gotenberg** | 🤖 Claude | Needs the compose stack (C3). The Plotly CDN must load inside Gotenberg's Chromium (internet access required), and the `waitDelay` may need tuning. |
| H9 | **Real-LLM agent quality** | 🤖 Claude | On the live OpenAI run the extraction agent **skipped the planned MOM Excel task** and called `fetch_datagov` without a title, so the dataset shows its raw id as the title. Fixes: tighten the prompt to work through every plan task; look the title up from the search result inside `fetch_datagov`. |
| H10 | **Correlation not shown in the main demo** | 🤖 Claude | In the main query the second dataset's (M651561) series names don't match the sector, so no correlation is computed. Either match the series better, or demo correlation with sample query 4 (internal programme data). Verify that query works. |

### Security / cost gaps in the code

| # | Item | Owner | Details |
|---|---|---|---|
| H11 | **Per-run LLM budget cap is not enforced** | 🤖 Claude | `RUN_LLM_BUDGET_USD` exists in config but **no code checks it** (plan.md §9/§11.1 claim it does). The router should stop or force mock once a run passes the cap. This matters for the public ECS URL. |
| H12 | **Chaos admin endpoint open to any token holder** | 🤖 Claude | `PUT /api/v1/admin/chaos` lets anyone with the access token break the deployed app. Disable it when `APP_ENV=aws`, or use a separate admin token. |

### AWS deployment (plan.md §11.1)

| # | Item | Owner | Details |
|---|---|---|---|
| H13 | **AWS account setup** | 👤 You | Root MFA, Identity Center admin + `aws configure sso`, **budget alert first**, region `ap-southeast-1`. |
| H14 | **Install tools** | 👤 You | **Not installed on this machine:** `aws` CLI v2, `terraform` ≥ 1.6, **`jq`** (used by `infra/scripts/deploy.sh`) and **`make`** (the Makefile targets; otherwise run the underlying commands directly). |
| H15 | **Terraform never validated** | 🤖 Claude (after H14) | Run `terraform fmt -check`, `terraform validate`, then `terraform plan`. Risky spots: the CloudFront prefix list in the ALB security group (counts about 55 rules toward the SG quota), the `master_user_secret` reference, and the managed CloudFront policy lookups. |
| H16 | **Fill `infra/terraform/aws/terraform.tfvars`** | 👤 You | Copy from `.tfvars.example`: `github_repo` (from C1), `alert_email`, `monthly_budget_usd`. |
| H17 | **`terraform apply`** | 👤 You approve | Creates billable resources (about US$3–4/day). Run only after you've reviewed the plan. Note: the ECS services can't pull an image until the first deploy (image tag `bootstrap` doesn't exist), which is expected. |
| H18 | **Set real secret values in AWS** | 👤 You | `aws secretsmanager put-secret-value --secret-id policy-analytics/app --secret-string file://secrets.json` (JSON keys: OPENAI_API_KEY, GOOGLE_API_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, TAVILY_API_KEY, **APP_ACCESS_TOKEN: must be a real value, since the URL is public**). Delete `secrets.json` afterwards. |
| H19 | **First deploy + check on CloudFront** | 👥 Both | `make aws-deploy` / `bash infra/scripts/deploy.sh`. Then check: the token screen, WebSocket through CloudFront, PDF export (Gotenberg sidecar), and `/readyz`. |
| H20 | **GitHub settings for `deploy-ecs.yml`** | 👤 You | Repo secret `AWS_DEPLOY_ROLE_ARN`. Repo variables `ECR_BACKEND`, `ECR_FRONTEND`, `CLUSTER`, `API_SERVICE`, `WEB_SERVICE`, `SUBNETS`, `TASKS_SG`, `APP_URL` (all from `terraform output`). A GitHub environment named `aws`. Then trigger the workflow once so the final version is deployed **by the pipeline**. |
| H21 | **Pause AWS after deploying** | 👤 You | `make aws-pause` (or `bash infra/scripts/pause.sh pause`) until the demo, and `make aws-destroy` after evaluation. RDS restarts automatically after 7 days stopped. |

### Evidence for TESTING.md

| # | Item | Owner | Details |
|---|---|---|---|
| H22 | **Coverage report** | 🤖 Claude | `pytest --cov`, numbers into TESTING.md (target ≥80% backend). Depends on C5. |
| H23 | **Load test run** | 🤖 Claude | Locust, headless, 50 users / 2 min, against the compose stack with `LLM_MODE=mock` and **Langfuse off** (protects the Hobby quota). Record p50/p95 and RPS. |
| H24 | **Hallucination metrics** | 🤖 Claude | Golden-fact checks for a few queries, the injection test, and a consistency check (same query × N on mock = identical facts; × 3 on live OpenAI if you approve the cost). Results go in TESTING.md. |

## 🟡 Medium: quality, honesty and polish

| # | Item | Owner | Details |
|---|---|---|---|
| M1 | **MOM Excel is a sample, not a real MOM download** | 👤 decide / 🤖 | `backend/data/mom/mom_employment_by_industry_sample.xlsx` holds real MOM-sourced figures (via Table Builder M182841) laid out in MOM's Excel format. It is labelled as such. Either download a real workbook from stats.mom.gov.sg and set `MOM_EXCEL_URL` (I'd need to check the parser on it), or keep it and disclose it clearly in DATA_SOURCES.md. |
| M2 | **Data.gov.sg search ranking is weak** | 🤖 Claude | "unemployment rate" returned an unrelated dataset first. Improve the query and title matching, or pin known dataset ids for the demo queries. |
| M3 | **Model ids and prices** | 👤 confirm | Defaults are `gpt-4.1` / `gpt-4.1-mini` and `gemini-2.5-pro` / `gemini-2.5-flash`. The prices in `backend/app/llm/costs.py` are approximate. Confirm the models you want and check the prices against the provider pages. |
| M4 | **Offline snapshots cover only the main query** | 🤖 Claude | Run each sample query once online to record snapshots, so the offline backup demo covers them all. Web pages are not snapshotted: offline + web needs `WEB_SEARCH_PROVIDER=mock`. |
| M5 | **Frontend lint and backend ruff never run** | 🤖 Claude | `npm run lint`, `ruff check`. CI runs both. |
| M6 | **Runner memory growth** | 🤖 Claude | `TaskRunner.contexts` keeps every run's DataFrames forever (used for CSV export and clarification resume). Evict finished runs after N minutes or keep the last K. |
| M7 | **One DB session per event** | 🤖 Claude | Fine for the demo; batch writes if the load test shows contention. |
| M8 | **Plan text out of date in places** | 🤖 Claude | plan.md §3 still mentions pandera, shadcn, uv and `langchain-mcp-adapters`. The actual choices are in decisions log items 11–13; update the §3 rows so docs and code agree. |
| M9 | **Cloud Run alternative not created** | 🤖 Claude | Moved to stretch by the re-baseline. At minimum write a DEPLOYMENT.md section with the AWS→GCP mapping (plan.md §11.2). The `infra/gcp/` files and `deploy-cloudrun.yml` are optional. |
| M10 | **Interpretation edge cases** | 🤖 Claude | Mock `interpret` defaults to the last 5 complete years and maps "tech" to "Information And Communications". Check "past 3 years" phrasing, multi-sector comparisons, and out-of-scope queries (e.g. "write me a poem") with both the mock and the live LLM. |
| M11 | **Frontend bundle size** | 🤖 Claude | Plotly makes the main chunk over 500 kB. Lazy-load the chart component. |
| M12 | **Frontend detail checks** | 🤖 Claude | Mobile layout, the chaos toggle knob positions (Tailwind `left-4.5`), long-claim wrapping, empty states. |

## 🟢 Low: stretch / nice to have

| # | Item | Owner | Details |
|---|---|---|---|
| L1 | Frontend unit tests (Vitest: timeline, WebSocket hook) | 🤖 | Moved to stretch by the re-baseline. |
| L2 | Playwright browser E2E | 🤖 | The CI smoke job covers the API path instead. |
| L3 | Third LLM provider | 🤖 | You already have `ANTHROPIC_API_KEY` set, so a Claude provider would be a cheap third fallback. Bedrock or Azure are alternatives. |
| L4 | Cross-provider LLM-as-judge (plan.md §10.2, layer 5) | 🤖 | Needs H1. |
| L5 | pgvector RAG (catalogue + past reports) | 🤖 | The SingStat MCP already covers discovery. |
| L6 | arq + Redis worker (horizontal scale-out) | 🤖 | Documented as the scale path; the app currently runs as a single replica. |
| L7 | Self-hosted Langfuse compose file | 🤖 | Documented option only. |
| L8 | Nightly workflows (live LLM eval, MCP contract test) | 🤖 | `nightly-llm-eval.yml` is in plan.md but not created. |
| L9 | CI security scans (pip-audit, npm audit, Trivy, gitleaks) | 🤖 | |
| L10 | Terraform remote state (S3 + lock) | 🤖 | Local state is fine for a single-user personal account. |
| L11 | `/datasets` page and cost dashboard in the UI | 🤖 | Cost is already shown per run. |
| L12 | Alembic migrations instead of `create_all` | 🤖 | Only needed once the schema changes after release. |
| L13 | markdownlint warnings in plan.md | 🤖 | Cosmetic. |

---

### Suggested order for today
1. **👤 now:** C1 (empty GitHub repo), C2 (`.env`), H1–H3 (keys), H13–H14 (AWS account + tools). These run in parallel with my work.
2. **🤖 morning:** C3 → C4 → H4–H10 → H11–H12 → C5 (tests) → H22–H24.
3. **🤖 + 👤 midday:** H15 → H16–H18 → H19 → H20.
4. **🤖 afternoon:** C6 + C7 docs → 👤 review → H21 pause → C8 rehearsal.
5. Medium and Low items only if time remains. **Feature freeze 1 pm**, per plan.md.
