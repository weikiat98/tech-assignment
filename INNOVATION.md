<!-- DRAFT for the author to edit so it reads in their own voice. Delete this line when done. -->

# Evolving the platform for secure government research

Building this platform taught me that the hard part of agentic analytics is not getting a model to
write a report. It is making a researcher able to **trust** that report, and keeping the system
working when real government data and services misbehave. My proposals build on the mechanisms that
already exist in the implementation, and on the failures I hit while building it.

## 1. Trust: from "verified" to "show your working"

Today every number in a report is a *Fact*: a deterministic computation with an id, a method and the
source table it came from. A rule-based verifier rejects any claim whose numbers, citations, years or
sectors don't match those Facts. In a mutation test it caught 150 of 150 injected hallucinations with no
false positives. The test also exposed a gap: claims with the right numbers attributed to the *wrong
sector* passed, until I added a check that the named sector is what the cited facts measure. That is
the pattern I want to extend: **every trust mechanism should come with an evaluation that can prove it
wrong.**

- **Provenance on hover, down to the source row.** Each number links to its tool call, the code path,
  and the raw rows of the source table and release it came from, plus a one-click export of a
  reproducible notebook for the analysis.
- **A semantic judge on a different provider.** The rule-based checks can't see a correct number with
  the wrong interpretation ("employment fell" when it rose). A judge model from a different provider
  than the writer would score each claim against its cited facts, and its agreement with the rules
  would be tracked over time.
- **Calibrated confidence.** Confidence badges should reflect the verifier and judge history for that
  type of claim, not the model's self-assessment.

## 2. Real-world data: expect the sources to change

Three of the hardest problems in this build came from the data sources, not the AI:

- The **SingStat MCP server rate-limited** a burst of my test runs (CloudFront 403s). I added a
  per-transport circuit breaker so the agent drops to the REST API instead of retrying a blocked server.
- The **Table Builder REST search** only matches the exact phrase, so the fallback silently picked a
  different table ("changes in employment" instead of "employment levels").
- **Data.gov.sg's search API ignores its query** and returns the same page for every search. I replaced
  it with a locally indexed catalogue.

None of these was an outage. Each was a *silent change in behaviour*, which is what makes them
dangerous. I would add:

- **Schema and behaviour contracts per source.** Nightly probes (the MCP advertises `listChanged`)
  compare tool lists, schemas *and* known-answer queries, e.g. "employment by sector must return
  M182841". On drift, an agent proposes an adapter fix that a human approves, so the source registry is
  self-healing but supervised.
- **Data vintages.** Statistics get revised. Every Fact should record the release it came from, so a
  report can say "based on the March 2026 release" and flag figures that have since been revised.
- **Uncertainty that travels.** Provisional values, interpolated gaps and annualised quarters already
  produce notes; these should propagate into each claim's wording and confidence.

## 3. Security and compliance in government environments

- **A data-classification-aware router.** The LLM router already does per-task model tiers, provider
  fallback, circuit breaking and per-run budget caps. The next step is routing by **data
  classification**: public open data may use commercial APIs, while Restricted or Sensitive internal
  data only goes to in-region private endpoints (e.g. Bedrock or Azure OpenAI in Singapore) or
  open-weight models on government infrastructure. Fallback must never cross a classification boundary.
- **An audit trail inside the boundary.** Tracing already records every prompt, response and tool call,
  with masking of keys and NRIC-like ids. Self-hosting it on GCC would make the full decision trail
  reviewable without data leaving government infrastructure.
- **Identity and least privilege.** Replace the shared access token with SSO, and add per-dataset
  access control so an agent only sees the tables its user is cleared for. Agents should act with the
  user's permissions, never a service account's.
- **Untrusted content stays data.** Web pages are already fenced, filtered for injection, limited to
  context unless from trusted domains, and fetched behind SSRF guards (including cloud metadata IPs).
  The same treatment should apply to any document a user uploads.

## 4. Collaboration and scale

- **Recurring briefs with diffs.** Most policy work repeats: a monthly labour-market brief, for
  example. Scheduled analyses that highlight what changed since last month, and which claims no longer
  hold, would save the most researcher time.
- **Team knowledge.** Comment threads on individual claims, and a shared library of approved reports
  that the planner retrieves (RAG) so new analyses reuse vetted dataset choices and caveats.
- **Scale.** The current single-process runner handled 50 concurrent users with 0 errors and a p95 of
  58 ms, but it is deliberately single-replica. The designed path is a Redis-backed worker queue and
  event stream, Postgres checkpoints, and pushing heavy aggregation into the database or DuckDB, so
  large tables never have to fit in one process.

## 5. Cost and resilience across clouds

Cost control works best when it is part of the design. ReAct steps already run on cheaper models,
synthesis on stronger ones, and each run has a hard budget after which it finishes on a scripted model
and says so. I would add **semantic caching** of repeated sub-tasks, **provider health scoring** that
routes by observed latency and error rate rather than a fixed order, and **evaluation-gated model
upgrades**: a new model version only goes into the router after it matches or beats the current one on
the hallucination evaluation and a golden set of questions.

The common thread is that an agentic platform for government should earn trust the same way a good
analyst does: show the working, state the caveats, and notice when the ground has shifted.
