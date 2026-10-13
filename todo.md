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
| A2 |~~Google Gemini key~~ 👤 | `GOOGLE_API_KEY` in `.env` is still a placeholder, so the second provider has never been called. With it I can test Gemini directly and the OpenAI → Gemini fallback. |
| A3 | **Review and edit docs** 👤 | Especially INNOVATION.md (written in your voice as a draft; remove the comment on line 1). |
| A4 | ~~Commit and push~~ 👥 | Nothing from 7 Oct is committed yet. Say the word and I'll commit in logical chunks and push to `origin/main`. CI then runs on GitHub for the first time. |
| A5 | **Repo visibility** 👤 | Public, or invite the assessors. |
| A6 | Demo rehearsal + backup recording (C8) 👤 | plan.md §15. Keep `OFFLINE_MODE=true` + `LLM_MODE=mock` as the fallback. |

## 🟠 AWS deployment (DEPLOYMENT.md §3)

**Redeployed 13 Oct** (42 resources applied under SSO profile `meow98`, `make aws-deploy` pushed `d65dd66`, `/readyz` OK at https://d2vrvoig653mbb.cloudfront.net; still up, so costs are accruing: `make aws-pause` or `aws-destroy` when done). A browser check on AWS (D5) and a live OpenAI run there are still outstanding.

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
| K3 | ~~DuckDuckGo live search~~ ✅ 13 Oct: live query returned 5 MOM/SingStat hits, all trust tier 1; `safe_fetch` + `extract_content` read a real MOM press release and the SSRF guard blocked `169.254.169.254`. **Tavily still untested** (needs `TAVILY_API_KEY`) | 👤 key, then 🤖 |
| K4 | ~~Confirm model ids and prices in `llm/costs.py` (M3)~~ | 👤 |
| M1 | ~~MOM workbook is a disclosed sample built from MOM-sourced figures; optionally point `MOM_EXCEL_URL` at a real MOM download~~ | 👤 decide |
| M7 | One DB session per event: fine at 50 users; batch if needed | 🤖 |
| M12 | Mobile layout, long-claim wrapping, empty states | 🤖 |

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

Reference: [radix-ui/primitives](https://github.com/radix-ui/primitives). These are unstyled, accessible
React primitives. Install the single **`radix-ui@^1.8.0`** package and import each primitive by subpath
(`import * as Tabs from "radix-ui/tabs"`) so unused ones are tree-shaken. Versions below 1.6.4 broke the
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
| U0 | Install `radix-ui`. Create a styled wrapper layer in `src/components/ui/`, one file per primitive, plus a `Button` that supports `asChild` through `Slot` so links and buttons share styles. Mount `Tooltip.Provider` and `Toast.Provider` in `main.tsx`. Add design tokens (surface, border, muted, agent colours) to `@theme`, a shared `focus-visible` ring, and enter/exit keyframes in `index.css`. Exit animations must be CSS **keyframe** animations: Radix `Presence` waits for `animationend` before unmounting, and transitions don't trigger it. | Slot, Portal | `components/ui.tsx` → `components/ui/*`, `main.tsx`, `index.css` |
| U1 | Controlled `Tabs.Root value={tab}` for the results tabs. The current auto-switch to Charts and back keeps working. Gains: arrow-key navigation, `tablist`/`tab`/`tabpanel` roles, `data-state=active` styling. | Tabs | `pages/RunView.tsx` |
| U2 | Replace `FactChip`'s CSS-hover popup with a Tooltip. The trigger becomes focusable, the content is portalled (so it is no longer clipped), and it repositions on collision. | Tooltip | `ResultPanels.tsx` |
| U3 | Use Switch + Label for the demo chaos toggles, "Include web context" and "show facts". This fixes the button-in-label markup and the invalid `left-4.5` knob class. | Switch, Label | `DemoControls.tsx`, `NewAnalysis.tsx`, `AgentTimeline.tsx` |
| U4 | Confirm before deleting a History item. Focus starts on Cancel, and Esc or an outside click can't confirm by accident. | AlertDialog | `pages/History.tsx` |

**Phase 2: run-view polish (all 🤖)**

| # | Item | Radix primitive | Where |
|---|---|---|---|
| U5 | Replace the four PDF/MD/JSON/CSV links with one "Export ▾" menu (keyboard and typeahead). History row actions (Re-run, Delete) move into a "⋯" menu. | DropdownMenu | `RunView.tsx`, `History.tsx` |
| U6 | Toasts for mutation errors (cancel, re-run, delete, clarify), "export started", and notable run events (LLM/source fallback, verification rewrite, run finished). They are announced through `aria-live`, and F8 focuses the toast region. | Toast | new `ui/toast.tsx` + hook |
| U7 | Make timeline events expandable: a keyboard-operable trigger, `aria-expanded`, and a height animation via `--radix-collapsible-content-height`. Data & quality: each dataset card's checks and cleaning-action lists collapse, with the score always visible. | Collapsible / Accordion | `AgentTimeline.tsx`, `ResultPanels.tsx` (DataPanel) |
| U8 | Add a stage progress bar to the run header: interpret → plan → extract → quality → analyse → write → verify, derived from events and indeterminate while queued. Rebuild `ScoreBar` on Progress to get `role="progressbar"` and its aria values. | Progress | `RunView.tsx`, `ui` |

**Phase 3: navigation, filtering, mobile (🤖, covers M12)**

| # | Item | Radix primitive | Where |
|---|---|---|---|
| U9 | Timeline filters by agent (coordinator, extraction, analytics, writer, verifier) and by event kind (reasoning, data, alerts), replacing the single "show facts" checkbox. Add a status filter to History, as plan.md §7 calls for. | ToggleGroup | `AgentTimeline.tsx`, `History.tsx` |
| U10 | Give the timeline pane and the event JSON viewer custom scrollbars while keeping native scrolling. Use the 1.7+ `ScrollArea.Content` pattern: `Viewport`'s implicit wrapper is deprecated. | ScrollArea | `RunView.tsx`, `AgentTimeline.tsx` |
| U11 | An "Expand" button on each chart opens it full-size in a modal Dialog, which needs a `Dialog.Title` (VisuallyHidden if needed). | Dialog, VisuallyHidden | `ChartsPanel` |
| U12 | Mobile (below `lg`): Activity and Results become two top-level tabs instead of the fixed 420 px column, as plan.md §7 describes. Long claims wrap, and every panel has a proper empty state. | Tabs | `RunView.tsx` |
| U13 | Clarification stays inline and non-modal, so the timeline stays visible. When the run enters `awaiting_input`, focus moves to the card and the question is announced via `aria-live`. Icon-only buttons get VisuallyHidden labels. | VisuallyHidden | `ClarificationCard.tsx` |
| U14 | Vitest + Testing Library tests: Tabs keyboard navigation, the AlertDialog confirm flow, Switch toggling, and the export menu. jsdom needs `ResizeObserver`, `hasPointerCapture` and `scrollIntoView` stubs for Radix. Overlaps L1. | | `frontend/src/**/*.test.tsx` |

**Checks and decisions**

| # | Item | Owner |
|---|---|---|
| U15 | ~~Approve adopting Radix~~ ✅ 13 Oct: recorded as decision 22 in plan.md §18, §3 and §7 updated. | 👥 |
| U16 | Measure the bundle after each phase against the decision-20 baseline (app shell 397 kB). Only subpath imports of the primitives we use should be pulled in. | 🤖 |
| U17 | ~~Refresh the look or only swap behaviour?~~ ✅ 13 Oct: **refresh the look too.** Before Phase 1, propose a concrete visual direction (type scale, palette incl. agent and status colours, density, light/dark) as U0 tokens, for your sign-off. | 👥 |
| U18 | After each phase: `npm run lint`, `typecheck`, `build`, `test`, plus a browser walk-through of the demo script (plan.md §15) with keyboard only. | 🤖 |

## 🟢 Stretch

L1 frontend unit tests (Vitest) · L2 Playwright E2E · L4 cross-provider LLM judge · L5 pgvector RAG ·
L6 arq + Redis worker · L7 self-hosted Langfuse compose · L8 nightly live-LLM eval and MCP contract
test · L9 security scans (pip-audit, npm audit, Trivy, gitleaks) · L10 Terraform remote state ·
L11 `/datasets` page and cost dashboard · L12 Alembic · Cloud Run files (documented in DEPLOYMENT.md §5).
