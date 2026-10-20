# TODO: open items

Snapshot: LLM providers stay **OpenAI + Google
Gemini** (decision 14).

**Owner:** 👤 **You** = manual step only you can do · 🤖 **Claude** = I can do it when you say go ·
👥 **Both** = I prepare, you review or approve.

## Done on 19 Oct (verified)

- **Docs audit** against the code: README, TESTING, ARCHITECTURE, DEPLOYMENT, CLAUDE.md and plan.md §3, §7, §8,
  §11, §12 corrected (chat API and schema, old page names, test counts 164 backend + 41 frontend, coverage 83%,
  Settings dialog, Alembic/Cloud Run/openapi-typescript claims that were never built). DATA_SOURCES.md and
  INNOVATION.md needed no changes.
- **uv + `uv.lock`** (decision 27): Dockerfile, CI, Makefile and docs moved off pip. Ruff and 164 backend tests
  pass on the locked environment; the image builds, imports the app, runs as `appuser` and has no dev tools in it.
  No `requirements.txt` (pyproject declares, `uv.lock` pins).
- **Monthly CVE scan** (decision 28): `.github/workflows/security.yml` (pip-audit, npm audit, Trivy). Each tool was
  run locally with the workflow's versions; findings below (S1-S3). Not yet run on GitHub.
- **CI** now runs the 41 Vitest tests (`npm test`) in the frontend job.
- **First-scan findings fixed** (S1-S3): nginx 1.30 base + `apk upgrade`, vite 7, vitest 4, react-router 7.
  Trivy, npm audit and pip-audit all clean locally (decision 29).
- **todo.md re-audit** against git, GitHub and the repo: struck everything finished or overtaken. Findings: all
  work up to 15 Oct is merged to `main` (PRs #1-#4, last `f21b971`); **AWS was destroyed on 15 Oct** (local
  Terraform state empty since 22:37, the CloudFront hostname no longer resolves); this machine's `backend/.venv`
  is already uv-managed; the repo is still private with no collaborators (A5).

## Test run, 19 Oct

Passed: backend `pytest -m "not contract and not llm"` **164 passed, 83% coverage**; `ruff` clean; hallucination
evaluation **150/150** flagged, 0 of 29 clean claims wrongly flagged; frontend ESLint, `tsc`, Vitest **41 passed (9
files)** and the production build (7.8 s). TESTING.md's figures already match this run.

**Done 20 Oct:** the load test and the CI smoke job now go through the chat API (`/chats`, follow-ups). Run locally against the offline MockLLM stack: load test 2,910 requests, 0 failures, p95 35 ms, p99 57 ms (TESTING.md §6 updated); the smoke job's script ran end to end (chat plus follow-up, both `completed`). The smoke job itself has not yet run on GitHub (see S4).

**Skipped on purpose (not run in this pass):**

| Item | Why skipped | Owner |
|---|---|---|
| Browser walk-through and exports (TESTING.md §8) | Manual: someone has to look at it. The keyboard-only demo script moved to Stretch (20 Oct) | 👤 |
| `-m contract` (live SingStat MCP) tests | Live service. Live-LLM checks (`-m llm`, OpenAI / Gemini) confirmed done by you on 20 Oct | 👤 |
| CI on GitHub (including the updated `smoke` job), `security.yml` | Not run on GitHub; see S4 | 👤 |

**Outdated entries in this file** (kept as history, superseded):

- ~~7 Oct block: "143 tests, 82% backend coverage" → now 164 tests, 83% (and 41 frontend tests).~~ (history; current figures are above)
- ~~7 Oct block: the load-test result and "Browser walk-through (C4)" were done against the old `/analyses` UI, before the chat layout (decision 24); re-run for the chat app.~~ (history; current figures are above)
- ~~U14 and U18 progress lines quote "18 Vitest tests" and "26 frontend tests"; the current count is 41.~~ (history; current figures are above)
- ~~Chat layout status quotes "157 backend tests" and "40 frontend tests"; current is 164 and 41.~~ (history; current figures are above)
- ~~A2, K1, K2 (Gemini key, live-LLM run of the sample queries, Langfuse)~~ ✅ 20 Oct: you confirmed all three as done. No result was written into the repo, so the figures are not recorded.
- ~~D5 (AWS browser check) is struck through, but the AWS section says the browser check and a live OpenAI run are "still outstanding".~~ Moot: AWS was destroyed 15 Oct; do it on the next deploy.

## 🔐 Security findings from the first scan (19 Oct; TESTING.md §9)

| # | Item | Owner |
|---|---|---|
| S1 | ~~**Frontend image:** `nginx:1.27-alpine` (Alpine 3.21.3) has 55 fixable CVEs, 2 critical (OpenSSL) and 53 high~~ ✅ 19 Oct: `nginx:1.30-alpine` (stable line, Alpine 3.24) + `apk upgrade` in the runtime stage; Trivy 0 high/critical. Compose stack verified (all healthy, `/readyz`, SPA deep links, `/api` and WebSocket proxying). Also fixed the Docker healthcheck, which the new Alpine broke (busybox `wget localhost` tries `::1`, nginx listens on IPv4 only; now `127.0.0.1`). AWS was destroyed on 15 Oct, so the next deploy ships the fixed image. | 🤖 |
| S2 | ~~**Frontend dev tooling:** vitest 2 (critical: tinypool prototype pollution → RCE) and vite 5 (high)~~ ✅ 19 Oct: vite 7.3.7 + @vitejs/plugin-react 5.2 + vitest 4.1.12 (vite 7 is patched and avoids vite 8's switch to Rolldown and plugin-react 6). Lint, typecheck, 41/41 tests and build pass. | 🤖 |
| S3 | ~~**react-router-dom 6** (moderate, shipped in the bundle): open redirect via backslash in `<Link>`/`useNavigate`~~ ✅ 19 Oct: react-router-dom 7.18.4, no code changes needed. Checked in Chrome against the compose stack: chat deep link, sidebar `NavLink` and `/activity` without page reloads, Home, `/analyses/:id` → its chat, `/history` → `/`. App shell 381 kB (was 370 kB). `npm audit`: 0 vulnerabilities. | 🤖 |
| S4 | Merge to `main` so the monthly schedule runs, then trigger it once by hand (Actions → Security scan). Optionally turn on Dependabot alerts (Settings → Code security) for continuous alerts between scans. | 👤 |
| S5 | ~~Everyone with a pip-made `backend/.venv`: install uv (`winget install astral-sh.uv` / `brew install uv`), then `make install`. The old `backend/policy_analytics_backend.egg-info` can be deleted.~~ ✅ 19 Oct on this machine: uv 0.12.23 installed and `backend/.venv` is already uv-managed (packages list `uv` as installer). The leftover `policy_analytics_backend.egg-info` is git-ignored and safe to delete. | 👤 |

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
| A2 | ~~Google Gemini key~~ ✅ 20 Oct: confirmed done by you | ~~`GOOGLE_API_KEY` in `.env` is still a placeholder, so the second provider has never been called.~~ |
| A3 | **Review and edit docs** 👤 | Especially INNOVATION.md (written in your voice as a draft; remove the comment on line 1, still there on 19 Oct). |
| A4 | ~~Commit and push~~ ✅ | ~~Nothing from 7 Oct is committed yet.~~ Everything up to 15 Oct is merged to `main` (PRs #1-#4, last `f21b971`). The 19 Oct changes on `dev` are not committed yet. |
| A5 | **Repo visibility** 👤 | Public, or invite the assessors. 19 Oct: still private, and you are the only collaborator. |
| A6 | Demo rehearsal + backup recording (C8) 👤 | plan.md §15. Keep `OFFLINE_MODE=true` + `LLM_MODE=mock` as the fallback. |

## 🟠 AWS deployment (DEPLOYMENT.md §3)

**Destroyed again on 15 Oct** (local Terraform state empty since 22:37; https://d2vrvoig653mbb.cloudfront.net no longer resolves), so nothing should be accruing. Not confirmed from the AWS side: the `meow98` SSO token has expired, so glance at the billing console. ~~Redeployed 13 Oct (42 resources, `make aws-deploy` pushed `d65dd66`, `/readyz` OK); still up, so costs are accruing.~~ A browser check on AWS (D5) and a live OpenAI run there were never recorded; do them on the next deploy.

**Previously destroyed on 9 Oct to stop costs** (all 42 resources; no leftovers, no DB snapshots). It was proven
working end to end on 8 Oct: Terraform apply, secrets, `make aws-deploy`, live at a CloudFront URL with
`/readyz` OK and the token enforced. Local `terraform.tfvars` (incl. the GitHub owner/repo ids) is kept,
so redeploying is: `make aws-plan` → `make aws-apply` → `infra/scripts/set-secrets.ps1` →
`make aws-deploy` (about 30 min, US$3-4/day while up).

| # | Item | Owner |
|---|---|---|
| D5 | ~~Browser check on AWS not done before destroy: token screen, live timeline (WebSocket via CloudFront), PDF export, a real OpenAI run~~ | 👥 next time it's up |
| D8 | ~~GitHub deploy workflow: OIDC login fixed (immutable-ID subject); last run failed on empty repo variables. After redeploying, update `APP_URL` (new CloudFront URL), check all 8 are under **Variables** (not Secrets) with exact names, then run the workflow~~ | 👤 |
| D9 | ~~Commit local changes: OIDC fix (`iam.tf`, `variables.tf`, `terraform.tfvars.example`), `deploy.sh` missing-settings message, `set-secrets.ps1`, docs~~ | 👤 |

## 🟡 With keys / nice to have

| # | Item | Owner |
|---|---|---|
| K1 | ~~Live-LLM run of every sample query (OpenAI, then Gemini): agent quality (H9), out-of-scope handling (M10), verification rates~~ | 🤖 (costs a few US cents per run) |
| K2 | ~~Langfuse: traces appear, LLM calls nest under the run, scores attach, masking works, "Open trace" link~~ | 🤖 after keys |
| K3 | ~~DuckDuckGo live search~~ ✅ 13 Oct: live query returned 5 MOM/SingStat hits, all trust tier 1; `safe_fetch` + `extract_content` read a real MOM press release and the SSRF guard blocked `169.254.169.254`. ~~Tavily still untested~~ ✅ 20 Oct: tested by you | 👤 |
| K4 | ~~Confirm model ids and prices in `llm/costs.py` (M3)~~ | 👤 |
| M1 | ~~MOM workbook is a disclosed sample built from MOM-sourced figures; optionally point `MOM_EXCEL_URL` at a real MOM download~~ | 👤 decide |
| M7 | One DB session per event: fine at 50 users; batch if needed | 🤖 |
| M12 | ~~Mobile layout, long-claim wrapping, empty states~~ ✅ U12 + CL7, checked at 390 px on 14 Oct (no real phone yet) | 🤖 |

## 🎨 Frontend UI enhancement with Radix Primitives (planned 12 Oct, approved 13 Oct, **built 13 Oct**)

**Status:** U0-U14, U16 and U18 are done: `radix-ui@1.8.1` installed, wrappers in `src/components/ui/`, all three
phases applied. Checks: lint and typecheck clean, 18 Vitest tests pass (tabs keyboard nav, AlertDialog flow,
Switch, export menu incl. `asChild`, toasts, progress, filters), build OK. **Bundle:** app shell 303 kB
(98.6 kB gzip), under the 397 kB baseline, because History and RunView are now lazy routes (RunView chunk
204 kB, loaded on demand). A browser walk-through on MockLLM found and fixed two defects: the export menu
crashed the app (`asChild` item with an icon sibling) and the timeline showed a stray horizontal scrollbar.
**Not verified:** screenshots of the final look (the automation tab was backgrounded, so checks were DOM-level),
the full keyboard-only demo script, and the mobile layout at a real phone width. **U17:** I kept the existing
blue/slate palette and added tokens (`canvas`, `surface`, `line`, `ink`, `muted`, agent colours) plus one focus
ring, rather than a full redesign; light mode only. Review it and say if you want a bolder direction.

**Review (14 Oct).** Re-ran every check: lint, typecheck, 18/18 tests and the build all pass, and the bundle
sizes match the figures above. The code covers U0-U14, and the review found these (all 🤖). **All fixed 14 Oct**
together with U17:

| # | Finding | Fix |
|---|---|---|
| R1 | ~~**U10 isn't done to spec.** `ui/scroll-area.tsx` renders `ScrollArea.Content` without `disableImplicitContentElement` on the Viewport. Radix therefore still adds its own deprecated `display: table` wrapper, with ours nested inside it (radix `scroll-area.tsx` L233-257). The `display: block` fix only applies to the inner element.~~ ✅ | ✅ 14 Oct: `disableImplicitContentElement` on the Viewport. |
| R2 | ~~The shared focus ring in `index.css` is unlayered CSS, and in Tailwind 4 unlayered CSS beats every utility (utilities live in `@layer utilities`). As a result `outline-none` on menu items is ignored and no component can restyle its own ring.~~ ✅ | ✅ 14 Oct: moved into `@layer base`. |
| R3 | ~~`ClarificationCard` puts `role="alert"` + `aria-live="assertive"` on a container that holds buttons and a form. Screen readers then announce the whole card, controls included.~~ ✅ | ✅ 14 Oct: `role="region"`, named by its heading and described by the question; focus still moves to it. Test added. |
| R4 | ~~The mobile Results/Activity switcher is a `Tabs` with no `TabsContent`, so each tab's `aria-controls` points at an id that doesn't exist.~~ ✅ | ✅ 14 Oct: single-select `ToggleGroup` view switch. |
| R5 | ~~Each timeline row's `CollapsibleTrigger` is a `<button>` containing a `<div>` and a `<p>`. Buttons may only contain phrasing content.~~ ✅ | ✅ 14 Oct: the row is built from spans. |
| R6 | ~~The toast replay guard compares the server's `e.ts` with the browser clock (`mountedAt - 5000`). If the client clock runs more than 5 s ahead of the server, every live toast is dropped.~~ ✅ | ✅ 14 Oct: the WebSocket now sends `{type: "replay_done", last_seq}` after its replay; the UI toasts only events after that seq. Backend and hook tests added. |
| R7 | ~~Docs and code disagree: decision 22 and this section say "subpath imports", but the code imports from the root `radix-ui` entry (only `Slot` uses a subpath). Tree-shaking still works: the shared Radix chunk is 39 kB.~~ ✅ | ✅ 14 Oct: decision 22 now says root `radix-ui` imports (tree-shaken). |
| R8 | ~~`--font-sans` names Inter, but Inter is never loaded (no `@font-face`, no link), so the app actually renders in Segoe UI or the system font.~~ ✅ | ✅ 14 Oct: IBM Plex Sans and Source Serif 4 self-hosted via `@fontsource` (latin subsets). |
| R9 | ~~The tokens are only partly applied: `StatusBadge`, `TierBadge`, `ClarificationCard`, report links and about 40 `text-slate-*` / `bg-slate-*` classes are still hard-coded.~~ ✅ | ✅ 14 Oct: every hard-coded `slate`/`blue`/`amber`/`red`/`emerald` class is now a token. |

**U18 progress (14 Oct):** lint, typecheck, 26 frontend tests, build, ruff and 144 backend tests pass. A browser
walk-through on MockLLM (offline) covered New analysis, the run view (Insights, Charts, Data & quality, Report,
timeline, live toasts) and History at 1440 px, and all three pages at 390 px. That pass found and fixed three
phone-width defects: the activity pane widened the page to 920 px (grid item without `min-w-0`), History's
visually hidden "Actions" label escaped its scroll box and widened the page, and the question column wrapped to
one word per line. The keyboard-only run of the demo script (now against the chat layout) moved to Stretch on 20 Oct.

**Finding (14 Oct), fixed 14 Oct:**

| # | Finding | Fix |
|---|---|---|
| R10 | ~~On SQLite (local dev), timestamps read back from the database have no timezone, so the browser treats UTC as local time: replayed timeline events and History show 4:58 AM for a run at 12:58 PM (UTC+8), while live events show the right time. Pre-existing; Postgres (`timestamptz`) is probably unaffected.~~ ✅ | ✅ A `UTCDateTime` column type returns timezone-aware values on SQLite; API and WebSocket timestamps now end in `Z`/`+00:00` (test added). |

Reference: [radix-ui/primitives](https://github.com/radix-ui/primitives). These are unstyled, accessible
React primitives. Install the single **`radix-ui@^1.8.0`** package and import from its root entry
(`import { Tabs } from "radix-ui"`); unused primitives are tree-shaken. Versions below 1.6.4 broke the
root-entry types. Peer deps list React `^16.8 … ^19`, so our React 18.3 works and no upgrade is needed.
Radix brings behaviour only (keyboard, focus, ARIA); it doesn't style anything. The look stays our
Tailwind 4 classes, applied through Radix's data attributes, e.g. `data-[state=open]:`,
`data-highlighted:` and `w-(--radix-select-trigger-width)`. This replaces the hand-rolled widgets that
have accessibility gaps:

- the tab bar is a set of plain buttons (no `tablist` role, no arrow-key navigation);
- the fact tooltip only appears on CSS hover, so keyboard users can't open it, and scrolling containers
  clip it;
- each demo toggle is a `<button>` inside a `<label>`;
- timeline rows are expanded by clicking an `<li>`;
- Delete in History has no confirmation;
- Cancel, Re-run and Delete fail silently.

**Phase 1: foundation and the biggest accessibility wins (all 🤖)**

| # | Item | Radix primitive | Where |
|---|---|---|---|
| U0 | ~~Install `radix-ui`. Create a styled wrapper layer in `src/components/ui/`, one file per primitive, plus a `Button` that supports `asChild` through `Slot` so links and buttons share styles. Mount `Tooltip.Provider` and `Toast.Provider` in `main.tsx`. Add design tokens (surface, border, muted, agent colours) to `@theme`, a shared `focus-visible` ring, and enter/exit keyframes in `index.css`. Exit animations must be CSS **keyframe** animations: Radix `Presence` waits for `animationend` before unmounting, and transitions don't trigger it.~~ ✅ | Slot, Portal | `components/ui.tsx` → `components/ui/*`, `main.tsx`, `index.css` |
| U1 | ~~Controlled `Tabs.Root value={tab}` for the results tabs. The current auto-switch to Charts and back keeps working. Gains: arrow-key navigation, `tablist`/`tab`/`tabpanel` roles, `data-state=active` styling.~~ ✅ | Tabs | `pages/RunView.tsx` |
| U2 | ~~Replace `FactChip`'s CSS-hover popup with a Tooltip. The trigger becomes focusable, the content is portalled (so it is no longer clipped), and it repositions on collision.~~ ✅ | Tooltip | `ResultPanels.tsx` |
| U3 | ~~Use Switch + Label for the demo chaos toggles, "Include web context" and "show facts". This fixes the button-in-label markup and the invalid `left-4.5` knob class.~~ ✅ | Switch, Label | `DemoControls.tsx`, `NewAnalysis.tsx`, `AgentTimeline.tsx` |
| U4 | ~~Confirm before deleting a History item. Focus starts on Cancel, and Esc or an outside click can't confirm by accident.~~ ✅ | AlertDialog | `pages/History.tsx` |

**Phase 2: run-view polish (all 🤖)**

| # | Item | Radix primitive | Where |
|---|---|---|---|
| U5 | ~~Replace the four PDF/MD/JSON/CSV links with one "Export ▾" menu (keyboard and typeahead). History row actions (Re-run, Delete) move into a "⋯" menu.~~ ✅ | DropdownMenu | `RunView.tsx`, `History.tsx` |
| U6 | ~~Toasts for mutation errors (cancel, re-run, delete, clarify), "export started", and notable run events (LLM/source fallback, verification rewrite, run finished). They are announced through `aria-live`, and F8 focuses the toast region.~~ ✅ | Toast | new `ui/toast.tsx` + hook |
| U7 | ~~Make timeline events expandable: a keyboard-operable trigger, `aria-expanded`, and a height animation via `--radix-collapsible-content-height`. Data & quality: each dataset card's checks and cleaning-action lists collapse, with the score always visible.~~ ✅ | Collapsible / Accordion | `AgentTimeline.tsx`, `ResultPanels.tsx` (DataPanel) |
| U8 | ~~Add a stage progress bar to the run header: interpret → plan → extract → quality → analyse → write → verify, derived from events and indeterminate while queued. Rebuild `ScoreBar` on Progress to get `role="progressbar"` and its aria values.~~ ✅ | Progress | `RunView.tsx`, `ui` |

**Phase 3: navigation, filtering, mobile (🤖, covers M12)**

| # | Item | Radix primitive | Where |
|---|---|---|---|
| U9 | ~~Timeline filters by agent (coordinator, extraction, analytics, writer, verifier) and by event kind (reasoning, data, alerts), replacing the single "show facts" checkbox. Add a status filter to History, as plan.md §7 calls for.~~ ✅ | ToggleGroup | `AgentTimeline.tsx`, `History.tsx` |
| U10 | ~~Give the timeline pane and the event JSON viewer custom scrollbars while keeping native scrolling. Use the 1.7+ `ScrollArea.Content` pattern: `Viewport`'s implicit wrapper is deprecated.~~ ✅ | ScrollArea | `RunView.tsx`, `AgentTimeline.tsx` |
| U11 | ~~An "Expand" button on each chart opens it full-size in a modal Dialog, which needs a `Dialog.Title` (VisuallyHidden if needed).~~ ✅ | Dialog, VisuallyHidden | `ChartsPanel` |
| U12 | ~~Mobile (below `lg`): Activity and Results become two top-level tabs instead of the fixed 420 px column, as plan.md §7 describes. Long claims wrap, and every panel has a proper empty state.~~ ✅ | Tabs | `RunView.tsx` |
| U13 | ~~Clarification stays inline and non-modal, so the timeline stays visible. When the run enters `awaiting_input`, focus moves to the card and the question is announced via `aria-live`. Icon-only buttons get VisuallyHidden labels.~~ ✅ | VisuallyHidden | `ClarificationCard.tsx` |
| U14 | ~~Vitest + Testing Library tests: Tabs keyboard navigation, the AlertDialog confirm flow, Switch toggling, and the export menu. jsdom needs `ResizeObserver`, `hasPointerCapture` and `scrollIntoView` stubs for Radix. Overlaps L1.~~ ✅ | | `frontend/src/**/*.test.tsx` |

**Checks and decisions**

| # | Item | Owner |
|---|---|---|
| U15 | ~~Approve adopting Radix~~ ✅ 13 Oct: recorded as decision 22 in plan.md §18, §3 and §7 updated. | 👥 |
| U16 | ~~Measure the bundle after each phase against the decision-20 baseline (app shell 397 kB). 14 Oct: app shell 303.7 kB (98.6 kB gzip), unchanged by U17; fonts load as separate files.~~ ✅ | 🤖 |
| U17 | ~~✅ **Built 14 Oct** to the signed-off direction (decision 23): dark-only tokens, IBM Plex Sans + Source Serif 4, evidence underline on cited numbers, Plotly dark layout, sentence case, 11 px floor.~~ ✅ | 👥 |
| U18 | After each phase: `npm run lint`, `typecheck`, `build`, `test`, plus a browser walk-through of the demo script (plan.md §15) with keyboard only. | 🤖 ✅ except the keyboard-only demo script, moved to Stretch 20 Oct |

### U17 visual direction: signed off and built 14 Oct

**Who it's for and what it must do.** Policy researchers at a Singapore ministry need a defensible, cited answer
and need to see how it was produced. The character to aim for is a statistics bureau's working desk: calm,
exact, and upfront about where every number comes from. It shouldn't look like a generic SaaS dashboard.

**The one bold element: an evidence mark.** Every cited number gets a yellow underline (changed from a
highlighter at sign-off), and the fact chips and the "Verified" stamp use the same yellow. Everything else stays quiet:
borders instead of shadows, one accent colour, and no decoration.

**Type**
- **IBM Plex Sans** for the interface. It has clear, distinct numerals, and tabular figures (`tnum`) keep columns
  of numbers aligned.
- **Source Serif 4** for the Report tab and the executive summary, so the verified report reads like a policy
  paper.
- `ui-monospace` only for raw JSON.
- Self-host both fonts with `@fontsource` (no CDN), so offline demo mode still renders correctly.
- Sentence case everywhere: drop the all-caps eyebrows, table headers and agent chips.
- Smallest text is 11 px (the timeline uses 10 px today).

| Token | Size / line height | Used for |
|---|---|---|
| `text-2xs` | 11 / 16 | chip and badge text, timestamps |
| `text-xs` | 12 / 16 | meta lines, table captions |
| `text-sm` | 13 / 20 | timeline, tables, menus (dense) |
| `text-base` | 14 / 22 | default UI text, insights |
| `text-md` | 16 / 26 | report body (serif, max 68ch) |
| `text-lg` | 19 / 26 | panel and section titles |
| `text-xl` | 24 / 30 | page titles, report title (serif) |

**Palette**
- Petrol teal replaces the generic Tailwind blue as the single accent (`brand-*` names are kept, so existing
  classes keep working).
- Surfaces are a cool grey-green (not cream, not slate).
- Every text/background pair below has a WCAG contrast of at least 4.5:1. I computed them in both themes.

```css
@theme {
  --font-sans: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --font-serif: "Source Serif 4", ui-serif, Georgia, serif;
  --font-mono: ui-monospace, "Cascadia Mono", Menlo, monospace;

  --color-canvas: #F4F6F5;        --color-surface: #FFFFFF;      --color-surface-sunken: #EBEFEE;
  --color-line: #D9E0DE;          --color-line-strong: #B9C4C1;
  --color-ink: #17242D;           --color-muted: #56656E;        /* 5.2-6.0:1 on all surfaces */
  --color-brand-50: #E6F2F1;      --color-brand-100: #CDE6E3;    --color-brand-500: #14897F; /* focus ring */
  --color-brand-600: #0B6E6E;     --color-brand-700: #095A5A;    /* white on 600 = 6.1:1 */
  --color-evidence: #F7E08A;      --color-evidence-ink: #5C4700; /* the evidence mark */
}
/* Dark: same token names, overridden on <html class="dark">, so components need no dark: variants. */
@layer base {
  .dark {
    --color-canvas: #0F171C;      --color-surface: #162128;      --color-surface-sunken: #1C2930;
    --color-line: #2A3A42;        --color-line-strong: #3B4E57;
    --color-ink: #E6ECEA;         --color-muted: #9AA9AF;
    --color-brand-50: #12302F;    --color-brand-100: #184240;    --color-brand-500: #4CC2B5;
    --color-brand-600: #3FB0A5;   --color-brand-700: #5CC4B8;    /* dark ink text on 600 = 6.9:1 */
    --color-evidence: #3A3212;    --color-evidence-ink: #F7E08A;
  }
}
```

**Status colours.** Each status is a text-on-tint pair. "Running" uses the accent because it is the live state.

| Status | Light (text / bg) | Dark (text / bg) | Contrast L / D |
|---|---|---|---|
| queued | `#46545C` / `#EBEFEE` | `#A6B3B9` / `#1F2B31` | 6.8 / 6.8 |
| running | `#0B5E5E` / `#E1F0EF` | `#7FD3C9` / `#12302F` | 6.5 / 8.1 |
| awaiting input | `#8A5300` / `#FCEFD3` | `#F2C46D` / `#3A2A0E` | 5.6 / 8.5 |
| completed | `#1E6B3A` / `#E3F3E8` | `#7BCF98` / `#12301D` | 5.7 / 7.7 |
| partial | `#9A4510` / `#FDE8D7` | `#F2A06B` / `#3A220F` | 5.5 / 7.1 |
| failed | `#A82822` / `#FBE3E1` | `#F28B82` / `#3A1614` | 5.7 / 6.7 |
| cancelled | `#5E6A71` / `#EEF0F1` | `#A6B3B9` / `#1F2B31` | 4.9 / 6.8 |

**Agent colours.** These deliberately avoid the status hues: today the verifier is rose (reads as error) and the
writer is amber (reads as warning). Light mode uses white text on a dark fill; dark mode uses ink text on a light
fill. `system` becomes an outlined chip with no fill.

| Agent | Light fill (white text) | Dark fill (ink text) | Contrast L / D |
|---|---|---|---|
| coordinator | `#4C4AA8` indigo | `#A9A6F0` | 7.4 / 8.1 |
| extraction | `#1F6A9A` harbour blue | `#7FB8DE` | 5.9 / 8.5 |
| analytics | `#8E3B78` plum | `#DDA0CC` | 6.9 / 8.6 |
| writer | `#66650F` olive | `#CFCB6A` | 6.1 / 10.7 |
| verifier | `#33414C` slate ink | `#B8C5CE` | 10.5 / 10.3 |

**Density and shape**
- 4 px grid.
- **Compact** where people scan (timeline, history and dataset rows: 32 px rows, 6/10 px padding);
  **comfortable** where people read (insights and report: 16-24 px gaps).
- Corner radius grows with hierarchy instead of one radius everywhere: chips 4 px, controls 6 px, panels 10 px,
  dialogs and toasts 14 px.
- Shadows only on floating layers (menus, tooltips, dialogs, toasts). Panels lose `shadow-sm` and are border-only.
- Motion stays as it is: only in response to an action, and reduced motion is respected.

**Theme: dark only (signed off).**
- The app ships a single dark theme. There is no light theme and no toggle, and `color-scheme: dark` is set on `<html>`.
- The dark values in the CSS block above become the base `@theme` values. The light values are kept only as a
  record of the proposal and are not built.
- Plotly: `PlotlyChart.tsx` applies one dark layout (transparent paper and plot background, font, grid and
  axis colours). The backend chart colorway is unchanged; aligning it is a follow-up using the dataviz
  palette method.
- PDF export stays light: Gotenberg renders the backend's own HTML, which is meant for print.

**Implementation (done 14 Oct):**
1. Fonts and dark tokens as the base theme, with R2 included.
2. Sweep the hard-coded `slate-*` / `blue-*` / `amber-*` classes onto tokens (R8, R9).
3. The evidence underline on cited numbers, plus the filled `FactChip` and Verified stamp.
4. Plotly dark layout.
5. Sentence-case and 11 px-floor cleanup.
6. Fix R1-R7.
7. Screenshots of every page at desktop and phone width, for review.

**Sign-off (14 Oct).** Your comments, and how each is applied:

| # | Item | Your comment | Applied as |
|---|---|---|---|
| a | Palette and accent | approved | As proposed (dark values). |
| b | Plex Sans + Source Serif 4 | approved | As proposed. |
| c | Evidence mark | "noticed highlight not completly highlighting entire text. suggest changing to underline. color unchanged." | Cited numbers get a 2 px underline in evidence yellow `#F7E08A`, offset 3 px; the text stays `ink`. The fact chip and the Verified stamp stay filled chips in the same yellow family. |
| d | Dark mode | "dark mode only." | One dark theme, no light theme or toggle. Correct me if you meant "ship dark mode now, light later". |

## 💬 Chat layout, search-engine style (mockup 14 Oct, approved as decision 24, **built 14 Oct**)

**Status (14 Oct):** CL1-CL14 and CL16 are built (decision 25). Checks: ruff clean, 157 backend tests, ESLint and
typecheck clean, 40 frontend tests, build OK (app shell 370 kB, Chat chunk 206 kB). Browser walk-through (DOM level;
the automation tab was backgrounded, so no screenshots): Home, sidebar, an existing chat, a follow-up ("What about
finance?" answered with its own facts), Preview panel, activity dialog, run details, and a 390 px iframe (drawer and
preview sheet, no sideways scroll). **Not verified:** screenshots of the final look; the keyboard-only demo script;
real OpenAI or Gemini runs of follow-ups and the model choice; a real phone. **Known limits:** a follow-up whose
earlier run has left memory loses the carried datasets; CL11 optional LLM-written titles not built; the activity
dialog lost the old per-agent filter.

**15 Oct follow-ups (decision 26):** Home wordmark spacing, menu tick alignment, a labelled Settings button, and a
**Run activity** page (`/activity`, sidebar link) with week/month/year totals, a running count and each period's
runs. Checks: ruff clean, 164 backend tests, ESLint and typecheck clean, 41 frontend tests; checked in Chrome at
desktop width (not on a phone).

**Mockup:** [Policy Analytics Chat Layout](https://claude.ai/artifact/CLZY6xXdULSwKDarDeJDGT) (private until shared).
It has 7 artboards in the signed-off dark theme (decision 23). Artboards 1-4 are clickable.

1. **Home:** a search-first start page, like Google. A centred wordmark ("OWL") and tagline sit above one
   rounded chat bar. The **+** button opens a menu: web context on/off and model (Auto / OpenAI / Google
   Gemini). The current options show as chips under the bar, with sample questions below. The gear (top right)
   opens **Settings**: system status and the demo controls.
2. **Chat:** collapsible sidebar on the left, chat thread in the middle, Preview panel on the right. Opening
   the preview collapses the sidebar; one toggle in the header reopens it. Every question and answer has Copy
   and Retry; Export offers .md, .pdf or .docx.
3. **Sidebar:** New chat; search; groups Pinned / Today / Previous 7 days / Older. Each chat has a ⋯ menu with
   Pin/Unpin, Rename (edited in place) and Delete (confirmed in a dialog).
4. **Agent activity, expanded:** 7 plain-language steps. You can switch between "Main steps" and "Every action";
   the raw JSON is under "Technical details".
5. **Run details** (low priority): what a non-technical user needs to know about a run.
6. **Phone:** the sidebar becomes a drawer and the preview a full-screen sheet.
7. **Today vs proposed:** real timeline events next to the plain sentence each would become.

**Why it's needed** (gaps in the current app):
- A finished run can't be continued. There are no follow-up questions and no concept of a conversation.
- The agent activity sits in its own panel beside the results, instead of in the conversation.
- The activity shows raw tool calls and JSON (`fetch_singstat({"resource_id": …})`, `{"via":"snapshot",…}`).
- The `provider_preference` field the API accepts is ignored: `llm_router` never reads it, so "change model"
  needs backend work.
- There is no pin, rename or search across past chats; History is a separate page.

**Mockup review (14 Oct):** the Chat artboard was cluttered and had overlaps. Fixed:
- The sidebar was squeezed narrower than its content, so the header's sidebar toggle sat on top of
  "New chat". It now has a fixed 320 px slot, and only one sidebar toggle is left (in the page header).
- Closing the preview hid the whole chat column (it was nested inside the preview's condition).
- Duplicates removed: a second "New chat", a second Export (Export now lives only in the Preview panel), and
  the "Preview" heading above the tabs.
- The answer had six separately boxed bands. Findings are now a plain list. The Verified stamp shares one row
  with Preview and Copy. The chat bar's caption no longer repeats the follow-up explanation.
- With all three columns open, the chat column was narrow, so opening the preview now collapses the sidebar.
- The Settings gear on Home had no function. It now opens the Settings dialog, and the duplicate "Settings and
  demo controls" link in the sidebar footer is gone.

### Phase A: new layout on the existing API (frontend only, 🤖)

Each existing analysis is shown as a one-question chat. The follow-up bar stays disabled until Phase B.

| # | Item | Where |
|---|---|---|
| CL1 | ~~**App shell.** Replace the top nav (New analysis / History) with a collapsible left sidebar, the main column and a right Preview panel. The sidebar's open/closed state is remembered per browser; opening the preview collapses it. One sidebar toggle, in the header. A Settings gear in the header on every page. `/history` redirects to `/`.~~ ✅ | `App.tsx`, new `components/Sidebar.tsx`, `components/ChatShell.tsx` |
| CL2 | ~~**Home.** Wordmark, tagline and a rounded chat bar. **+** opens a menu with: Include web context (switch) and Model (Auto / OpenAI / Google Gemini; radio items). The chosen options show as chips under the bar, with sample questions below. The System card and the chaos toggles move into a **Settings** dialog opened from the header gear (CL-e).~~ ✅ | `pages/NewAnalysis.tsx` → `pages/Home.tsx`, `ui/dropdown-menu` (checkbox/radio items) |
| CL3 | ~~**Chat thread.** The question is a user bubble. The answer is today's Insights content: Verified stamp, serif summary, findings (a plain list) with the evidence underline and fact chips. Under it, one row: Preview, Copy and the Verified stamp; then follow-up suggestion chips. Export lives only in the Preview panel. **Copy and retry on every turn**, in every chat (new, existing, and old analyses shown as one-question chats): each question has Copy and "Ask this question again" under its bubble; each finished answer has Copy and Retry in its action row. A retry adds a new answer version and keeps the earlier one, with "‹ Answer 2 of 2 ›" to switch between them; a running answer shows Stop instead of Retry. "Copied" confirms a copy. Until CL9 lands, a retry starts a fresh analysis with the same question. The chat bar sits at the bottom, with a Stop button while a run is going. A clarification becomes an assistant message with suggestion chips, answered from the chat bar.~~ ✅ | `pages/RunView.tsx` → `pages/Chat.tsx`, `ClarificationCard.tsx` |
| CL4 | ~~**Activity inside the answer, collapsed by default.** While running, one line reads e.g. "Step 3 of 7: collecting data from SingStat". When done it reads "Researched in 7 steps · 4 data sources · 1 note · 2 s". **Show steps** expands the 7 stages; "Open the full activity" opens the full view (artboard 4) in a dialog. The separate Agent activity panel goes away.~~ ✅ | `AgentTimeline.tsx` → `ActivitySummary.tsx` + `ActivityDialog.tsx` |
| CL5 | ~~**Preview.** A split button: **Preview** opens the panel on **Report**; **▾** picks Charts, Data & quality, Report or Plan directly. The panel has the same four tabs plus Export and Close. **Export** opens a menu: Markdown (.md), PDF (.pdf) or Word (.docx); .docx needs CL16. JSON and CSV stay in the API but leave the menu. Each answer has its own preview. On a phone it opens as a full-screen sheet.~~ ✅ | `ResultPanels.tsx` (reused as the tab bodies), new `PreviewPanel.tsx` |
| CL6 | ~~**Sidebar.** New chat; search; the groups above. Each row's ⋯ menu has Pin/Unpin, Rename (edited in place) and Delete (confirmed in an AlertDialog, CL-d). The active chat is highlighted. Needs CL9 for pin and rename; until then, show search and delete only.~~ ✅ | `Sidebar.tsx` |
| CL7 | ~~**Phone.** Sidebar as a drawer, preview as a sheet, chat bar fixed to the bottom. Check at 390 px with no sideways scrolling, as in U18.~~ ✅ | shell + `PreviewPanel.tsx` |
| CL8 | ~~**Plain-language activity.** A pure formatter `lib/activity.ts` turns events into the 7 stages (reusing `lib/stages.ts`), using a sentence template per event type and a verb per tool, e.g. `singstat_search_tables` → "Searched SingStat for “…”", `fetch_singstat` → "Downloaded … from SingStat", `singstat_get_metadata` → "Read the table's details", `make_chart` → "Drew a … chart". Fallbacks become amber "Note" lines. Quality events become a score sentence. Facts and report chunks are counted, not listed. Hand-offs mark stage boundaries. Task ids ("T1:") are stripped from thoughts. "Main steps" / "Every action" switch, with the JSON under "Technical details". Unit-tested on events recorded from the sample queries.~~ ✅ | new `lib/activity.ts` + tests |

### Phase B: conversations and follow-ups (backend + frontend, 🤖)

| # | Item | Where |
|---|---|---|
| CL9 | ~~**Chats.** New `chats` table (id, title, pinned, created_at, updated_at), plus `analyses.chat_id`, `turn` and `version` (a retry adds a version to the same turn; the newest is shown, older ones stay reachable). Existing analyses each become a one-question chat. `POST /chats/{id}/turns/{turn}/retry` re-runs a turn with the same question and the context of the turns before it. Endpoints: `POST /chats` (first question), `GET /chats?q=` (searches titles and questions; pinned first), `PATCH /chats/{id}` (title, pinned), `DELETE /chats/{id}` (cascades to its runs), `POST /chats/{id}/messages` (follow-up → new analysis in the chat). `/analyses/*` stays for single runs and exports. Needs R10 (timezone) fixed first, since the sidebar groups chats by date.~~ ✅ | `db/models.py`, `api/chats.py`, `db/init.py` |
| CL10 | ~~**Follow-up context (the biggest item).** The coordinator receives the previous turns (question, executive summary, fact list, dataset keys), so it can resolve "this" or "the same years" and reuse datasets already collected instead of fetching them again. The verifier accepts facts from earlier turns as citations. Needs prompt and MockLLM policy changes, plus graph tests for one follow-up per sample query.~~ ✅ | `agents/graph.py`, `prompts.py`, `mock_policies.py`, `verification/checks.py` |
| CL11 | ~~**Chat title.** Default: the first question, trimmed. Later, optionally, a short title from the fast model tier.~~ ✅ default title (`api/runs.py` `title_from`); the optional LLM-written title was not built | `api/chats.py` |
| CL12 | ~~**Model choice.** Make `llm_router` honour `provider_preference`: `auto` keeps the current OpenAI → Gemini chain; `openai` or `gemini` puts that provider first. Run details show the provider actually used.~~ ✅ | `llm/router.py`, `api/schemas.py` |
| CL16 | ~~**Word export.** Add `format=docx` to `GET /analyses/{id}/export`, built from the structured result (title, verification line, headings, findings, limitations, sources) with `python-docx`, charts embedded as images where the PDF path already renders them. Test that every number in the .docx matches the Markdown export.~~ ✅ | `export/docx.py`, `api/analyses.py` |
| CL13 | ~~**Follow-up suggestions.** Three short next questions per answer, either from the writer or built deterministically from the intent (another sector, other years, retrenchments).~~ ✅ | writer or `agents/vocab.py` |

### Phase C: run details for non-technical users (low priority, 🤖)

| # | Item | Where |
|---|---|---|
| CL14 | ~~**Run details (artboard 5).** Open from the sidebar ("Run activity") or from an answer. Lists the chat's runs; for the selected one it shows: outcome and Verified, time taken, AI model actually used (with any fallback), cost, steps and retries, each data source as Live / Saved copy / Failed, the checks, and a "Worth knowing" box (fallbacks, removed claims, low quality). The Langfuse trace link is kept only as "for engineers", and only when Langfuse is configured.~~ ✅ | new `GET /analyses/{id}/summary`, `RunDetails.tsx` |
| CL15 | ~~**Why not just Langfuse:** it shows every span, prompt and token count, which is right for engineers but overwhelming for researchers. Everything artboard 5 needs is already in our own `agent_events`, `llm_calls` and the result (verification, datasets with `is_fallback`). One endpoint can aggregate it with no extra tracing cost.~~ ✅ applied in CL14 | design note |

### Decisions (all proposals approved 14 Oct; recorded as decision 24)

| # | Question | Decision |
|---|---|---|
| CL-a | ~~Is the answer in the chat the old Insights tab, so Preview only has Report, Charts, Data & quality and Plan?~~ | ✅ Yes |
| CL-b | ~~When you pick OpenAI or Gemini: is that strict, or preferred with the other as fallback?~~ | ✅ Preferred, with fallback |
| CL-c | ~~Should a follow-up reuse data the chat already collected, or always start a fresh run?~~ | ✅ Reuse, and fetch only what's new |
| CL-d | ~~Delete: confirm in place in the sidebar, or in a dialog (today's AlertDialog)?~~ | ✅ Dialog (mockup updated) |
| CL-e | ~~Demo controls: in the Settings dialog, or in the **+** menu?~~ | ✅ Settings (mockup updated) |
| CL-f | ~~Record as decision 24 in plan.md and rewrite §7 (routes and layout).~~ | ✅ Done 14 Oct |

## 🟢 Stretch

Keyboard-only run of the demo script (plan.md §15, moved from U18 on 20 Oct) · ~~L1 frontend unit tests (Vitest)~~ ✅ 41 tests, in CI since 19 Oct · L2 Playwright E2E · L4 cross-provider LLM judge · L5 pgvector RAG ·
L6 arq + Redis worker · L7 self-hosted Langfuse compose · L8 nightly live-LLM eval and MCP contract
test · L9 security scans: ✅ pip-audit, npm audit, Trivy monthly (19 Oct); gitleaks and a Terraform IaC scan still open · L10 Terraform remote state ·
L11 `/datasets` page and cost dashboard · L12 Alembic · Cloud Run files (documented in DEPLOYMENT.md §5).
