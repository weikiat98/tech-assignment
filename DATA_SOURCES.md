# Data sources

Five sources feed the Extraction agent. Together they cover JSON APIs (MCP and REST), CSV, Excel, SQL
and HTML. All of them normalise to one canonical long format (`source_id, dataset_id, series,
series_code, period, period_start, frequency, value, unit`) with provenance attached: URL, retrieval
time, fallback flag and reason, agency, footnote and trust tier.

| Source | Access | Format | Auth | Role |
|---|---|---|---|---|
| DOS SingStat | **SingStat MCP server**, then Table Builder REST, then snapshot | JSON | none | Primary official statistics |
| Data.gov.sg | v2 public API + signed CSV download (local catalogue index for search) | CSV | optional API key | Cross-source check, CSV path |
| MOM | Excel workbook (URL or bundled sample) | XLSX | none | Excel path, cross-check of SingStat |
| Internal systems (mock) | SQL on the app database | SQL | n/a | Programme and grant data for policy-vs-outcome analysis |
| Web | Tavily, then DuckDuckGo, then fixtures; SSRF-safe fetch | HTML, linked CSV/XLSX | Tavily key optional | Qualitative context, files not in catalogues |

Licences: data.gov.sg datasets are under the
[Singapore Open Data Licence](https://data.gov.sg/open-data-licence); SingStat Table Builder data is
subject to the [SingStat terms of use](https://www.singstat.gov.sg/terms-of-use). Following the
SingStat MCP's attribution rule, only values returned by the source are attributed to it. Derived
values (growth rates, shares, correlations, projections) are labelled in every report as computed by
this platform.

## 1. DOS SingStat

### Primary: the SingStat MCP server

DOS publishes an official [Model Context Protocol](https://modelcontextprotocol.io) server in front of
SingStat Table Builder (2,800+ tables from 70 agencies).

- Endpoint: `https://chatwithsandra.singstat.gov.sg/mcp` (streamable HTTP, stateless, no auth;
  `DOSTableBuilderMCP` v3.2.4, protocol `2025-06-18`, verified 3 Oct 2026)
- Client: the official `mcp` Python SDK (`streamable_http_client` + `ClientSession`), one short session
  per call

| MCP tool | Agent tool | Use |
|---|---|---|
| `get_relevant_table_names(query_text)` | `singstat_search_tables` | Discovery: tables grouped by title → {frequency: resource id} |
| `get_table_metadata(resource_id)` | `singstat_get_metadata` | Units, `startPeriod`/`endPeriod`, `dataSource` agency, footnotes, series list (`seriesNo`, `rowText`, `uoM`) |
| `get_table_data(resource_id, seriesNoORrowNo, timeFilter, offset)` | `fetch_singstat` (wrapped) | Data, max 3,000 rows per call. Wrapped so every fetch goes through normalisation, snapshot, quality checks and provenance |

Tables used by the sample queries:

| Id | Title | Frequency | Used for |
|---|---|---|---|
| M182841 | Employment (Persons) By Sector (As At Year-End) | Annual | Main employment series (MOM data); sector shares |
| M651561 | Employed Tech And Media Manpower By Sector | Annual | Second view of tech employment (IMDA) |
| M183881 | Retrenched Permanent Employees By Industry (SSIC 2020) And Occupational Group | Quarterly | Retrenchment questions (annualised) |
| M183901 | Changes In Employment By Sector (Compared To The Previous Period) | Annual | Seen in search; ranked below level tables |

### Fallback 1: Table Builder REST API

`https://tablebuilder.singstat.gov.sg/api/table/` with the same resource ids:
`resourceid?keyword=...&searchOption=all`, `metadata/{id}`, `tabledata/{id}?limit=3000`. The adapter
maps REST responses to the MCP's shapes, so the rest of the pipeline doesn't know which transport served
the data.

### Fallback 2: recorded snapshots

Every live response is saved under `backend/data/snapshots/singstat/`, keyed by tool and arguments.
With both transports down, or `OFFLINE_MODE=true`, the adapter replays the latest recording and marks
the dataset as a fallback with the recording time.

### Quirks found and how they're handled

| Quirk | Handling |
|---|---|
| Values come back as strings (`"451.2"`), sometimes with markers (`-`, `na`) | `parse_value` converts numbers and turns markers into missing values for the quality pipeline |
| Units vary per row (`Thousand`, `Number`, `Per Cent`) | Unit kept per row; formatting and validity checks are unit-aware |
| Hierarchical series numbers (`3` Services → `3.4` Information And Communications), with gaps | Parent-vs-children consistency check; a footnote says totals may not add up because of rounding, so the check tolerates 2% and reports larger gaps as info |
| Mixed period formats (`2024`, `2023 3Q`, `2023 Jan`) | `parse_period` normalises them to `2024`, `2023-Q3`, `2023-01` with a start date and frequency |
| Table footnotes and caveats | Kept on the dataset and surfaced as quality info and report limitations |
| **REST search is a substring match on the whole phrase**: "employment by sector" misses "Employment (Persons) By Sector" | The fallback searches each distinctive keyword separately, ranks by keyword overlap, and ranks derived tables ("Changes in…", "Compared to…") below level tables unless the question asks for changes |
| **The MCP sits behind CloudFront and rate-limits bursts**: about a dozen back-to-back runs got `403 Request blocked` for several minutes | Per-transport circuit breaker: 2 failed calls, or any 403/429, skip the MCP for 2 minutes and go straight to REST, instead of retrying a blocked server on every call. Simulated (chaos) outages never trip the real breaker. Load tests run offline |
| Fallback responses could overwrite the MCP recording, so the offline demo inherited REST's weaker ranking | Fallback responses only fill gaps in the snapshot store; they never replace a primary recording |

## 2. Data.gov.sg

- Catalogue: `GET https://api-production.data.gov.sg/v2/public/api/datasets?page=N` (10 per page)
- Download: `GET https://api-open.data.gov.sg/v1/public/api/datasets/{id}/poll-download` returns a signed
  CSV URL
- JSON fallback: CKAN `datastore_search?resource_id={id}`
- Optional `DATAGOV_API_KEY` (sent as `x-api-key`) raises rate limits

Dataset used by the sample queries: `d_000d49cda016c13522d7d5be6a050f59`, *Number of Retrenched
Employees - Quarterly* (MOM), as a labour-market cross-check. The CSV is parsed by detecting the period
column (`year`, `quarter`, `month`, ...) and unpivoting the value columns.

**Quirk: the v2 search API ignores its query.** `?query=unemployment` (also `q=`, `search=`,
`keyword=`, `searchTerm=`) returns the same first page of the whole catalogue in id order, and there is
no public search endpoint. A search for "retrenched employees" only appeared to work because that
dataset happens to sort second. `python -m app.scripts.build_datagov_index` pages through the catalogue
once (4,643 active datasets, one request at a time, about 3 a second) and writes a 1.9 MB index to
`backend/data/datagov_catalogue.json`. The adapter searches it locally by keyword: title matches count
triple, ties go to the more general title, then the most recent update. Re-run the script to pick up new
datasets. Without the index, the adapter falls back to the live API.

## 3. MOM statistics (Excel)

MOM publishes labour-market tables as `.xlsx` with title rows, a unit row, multi-row headers, footnotes
and markers (`-` for nil, a trailing `p` for provisional values such as `123.4p`). The adapter (`sources/mom.py`):

1. takes the workbook from an explicit URL (e.g. one found by the agent's web search), then
   `MOM_EXCEL_URL`, then the bundled sample;
2. finds the header row as the first row with several year-like cells;
3. reads the unit from the rows above;
4. stops at footnote rows (`Note`, `Source`, `*`);
5. turns markers into missing values and unpivots wide to long.

**Disclosure:** the bundled `backend/data/mom/mom_employment_by_industry_sample.xlsx` is a *sample*, not a
file downloaded from stats.mom.gov.sg. `python -m app.scripts.build_samples` builds it in MOM's
publication layout from MOM-sourced figures (*Employment (Persons) By Sector*, SingStat M182841, whose
data source is MOM), and the workbook says so in its second row. It exercises the Excel path end to end
with real figures. Pointing `MOM_EXCEL_URL` at a real MOM workbook uses the same parser.

## 4. Internal systems (mock)

Two tables in the app database simulate internal agency systems, reached by SQL through
`query_internal_db`:

| Table | Columns | Content |
|---|---|---|
| `internal_programme_enrolments` | year, sector, programme, enrolled, completed, placed_in_jobs | Two training programmes across 6 sectors, 2019-2025 |
| `internal_grant_disbursements` | year, sector, scheme, amount_sgd_m, firms_supported | Two grant schemes, same sectors and years |

The data is **synthetic** and generated deterministically (`random.Random(42)` in `app/db/init.py`). Each
sector has a base level and growth rate, a COVID-19 dip in 2020, and plausible completion (78-90%) and
placement (62-80%) ratios, so analyses such as "enrolments vs placements" have something real to find.
Reports that use it say it is synthetic.

## 5. Web search and extraction

Used when official sources lack something, or for qualitative context ("what did MOM say?").

- **Search**: Tavily (`TAVILY_API_KEY`), then DuckDuckGo (`ddgs`, keyless), then skip. `mock` serves
  fixtures for tests and offline demos.
- **Fetch** (`web/fetch.py`): http(s) only; DNS resolved and private, loopback, link-local, reserved and
  multicast addresses blocked, including the AWS metadata IPs `169.254.169.254` and `169.254.170.2`;
  redirects re-checked (max 3); 10 s timeout; 5 MB limit; content-type allowlist. Text is decoded as
  UTF-8, falling back to Windows-1252.
- **Extract**: trafilatura for main text, `pandas.read_html` for tables, links to CSV/XLSX files.
- **Trust tiers**: tier 1 `*.gov.sg`; tier 2 World Bank, ILO, IMF, OECD, UN, ADB; tier 3 everything
  else, which is context only and can never become a numeric Fact.
- **Safety**: injection phrases are detected and stripped, page text is wrapped in
  `<untrusted_content>`, extracted numbers must literally appear in the page (grounding check), and
  each run is capped (`WEB_MAX_SEARCHES_PER_RUN`, `WEB_MAX_FETCHES_PER_RUN`).

## 6. Snapshots and offline mode

`backend/data/snapshots/` holds recorded responses for every sample query: MCP search, metadata and data
for SingStat, and search results and CSVs for Data.gov.sg. They serve three purposes:

1. **Fallback** when a live source fails (marked in the report).
2. **Offline demo**: `OFFLINE_MODE=true` serves everything from recordings. Web pages are not recorded,
   so offline runs with web context use `WEB_SEARCH_PROVIDER=mock`.
3. **Deterministic tests and CI**: the test suite runs offline.

Re-record after a data release with `make samples`, or by running the sample queries online.

## 7. Sector harmonisation

Sources name sectors differently ("Information And Communications", "ICT", "infocomm", "tech").
`agents/vocab.py` maps query keywords to SSIC-style sector names, and the verifier only accepts sector
names it can find in the collected data.
