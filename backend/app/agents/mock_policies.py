"""Scripted MockLLM policies.

When no LLM key is configured (or every provider fails), these functions stand in for
the model. They are deterministic and decide from the *real* observations of the run,
so the tools, data sources, quality checks, analytics and verifier all still execute.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from app.agents.vocab import DATAGOV_SEARCH, SINGSTAT_SEARCH, match_metrics, match_sectors
from app.core.chaos import chaos
from app.core.models import Claim, PlanTask, ReActStep, ReportDraft, ResearchIntent, ResearchPlan
from app.core.run_context import RunContext


def default_years() -> tuple[int, int]:
    end = date.today().year - 1
    return end - 4, end


# --- Coordinator -----------------------------------------------------------------------


def interpret(query: str, options: dict[str, Any], allow_clarification: bool = True) -> ResearchIntent:
    low = query.lower()
    years = sorted({int(y) for y in re.findall(r"\b(19[89]\d|20[0-4]\d)\b", query)})
    start, end = (years[0], years[-1]) if len(years) >= 2 else default_years()
    if len(years) == 1:
        start, end = years[0], default_years()[1]
        # "why did X rise in 2023?" asks about an event year: include the years before it for context.
        if re.search(rf"\b(in|during)\s+{years[0]}\b", low):
            start = years[0] - 3
    sectors = match_sectors(query)
    metrics = match_metrics(query)
    analysis = ["trend"]
    if re.search(r"correlat|relationship|relate", low):
        analysis.append("correlation")
    if re.search(r"forecast|project|predict|outlook", low):
        analysis.append("forecast")
    if re.search(r"compare|comparison|versus|vs\.?|across sectors", low):
        analysis.append("comparison")
    wants_web = bool(options.get("web_context")) or bool(re.search(r"\bwhy\b|reason|news|what did|context|explain",
                                                                   low))
    internal = "programmes" in metrics
    vague = not sectors and len(metrics) <= 1 and len(years) == 0 and len(query.split()) <= 8
    if allow_clarification and vague:
        return ResearchIntent(
            topic=query, needs_clarification=True, confidence=0.35,
            clarification_question="Which part of the job market should I analyse?",
            clarification_suggestions=[
                "Employment trends by sector, 2020-2024",
                "Retrenchments in the technology sector, 2019-2024",
                "Job vacancies across industries, 2021-2024",
            ],
            reasoning="The question names no sector, metric or period, so the analysis scope is ambiguous.",
        )
    if not metrics:
        metrics = ["employment"]
    sector_text = ", ".join(sectors) if sectors else "all sectors"
    return ResearchIntent(
        topic=f"{', '.join(metrics).capitalize()} in {sector_text}, {start}-{end}",
        sectors=sectors, metrics=metrics, start_year=start, end_year=end, analysis_types=analysis,
        wants_web_context=wants_web, uses_internal_data=internal, confidence=0.85,
        reasoning=(f"Focus on {', '.join(metrics)} for {sector_text} between {start} and {end}"
                   + ("; qualitative web context requested." if wants_web else ".")),
    )


def plan(intent: ResearchIntent, feedback: str | None = None) -> ResearchPlan:
    tasks: list[PlanTask] = []
    n = 0

    def add(**kw) -> None:
        nonlocal n
        n += 1
        tasks.append(PlanTask(id=f"T{n}", **kw))

    for metric in intent.metrics:
        if metric in SINGSTAT_SEARCH:
            add(agent="extraction", source="singstat", query=SINGSTAT_SEARCH[metric][0],
                description=f"Find and fetch official {metric} data by sector from SingStat (MCP)")
    if "employment" in intent.metrics and "Information And Communications" in intent.sectors:
        add(agent="extraction", source="singstat", query="employed tech and media manpower",
            description="Fetch tech & media manpower as a second view of the technology workforce")
    if "employment" in intent.metrics:
        add(agent="extraction", source="mom", query="employment by industry",
            description="Load MOM's employment-by-industry workbook (Excel) as a cross-source check")
    for metric in intent.metrics:
        if metric in DATAGOV_SEARCH:
            add(agent="extraction", source="datagov", query=DATAGOV_SEARCH[metric],
                description=f"Fetch Data.gov.sg CSV ({DATAGOV_SEARCH[metric]}) as labour-market context")
            break
    if intent.uses_internal_data:
        add(agent="extraction", source="internal", query="programme_enrolments",
            description="Query internal programme outcomes (enrolments, placements) by sector")
    if intent.wants_web_context:
        add(agent="extraction", source="web", query=f"Singapore {intent.topic} labour market report",
            description="Search the web for qualitative context (official sources preferred)")
    ext_ids = [t.id for t in tasks]
    add(agent="analytics", description="Compute levels, change, CAGR, YoY and trend for the focus sectors; shares "
        "of the total; correlations across datasets; " + ("forecast; " if "forecast" in intent.analysis_types else "")
        + "build charts", depends_on=ext_ids)
    add(agent="writer", description="Write a cited policy report", depends_on=[f"T{n}"])
    reasoning = "Official statistics from SingStat first, cross-checked with MOM and Data.gov.sg"
    if feedback:
        reasoning += f"; re-planned after: {feedback}"
    return ResearchPlan(reasoning=reasoning, tasks=tasks)


# --- Extraction (ReAct) ----------------------------------------------------------------


def _done(history: list[dict], action: str, **match) -> dict | None:
    for h in history:
        if h["action"] != action:
            continue
        if all(h["input"].get(k) == v for k, v in match.items()):
            return h
    return None


def _step(thought: str, action: str, args: dict | None = None, final: str | None = None) -> ReActStep:
    return ReActStep(thought=thought, action=action, action_input_json=json.dumps(args or {}), final_answer=final)


def _pick_table(tables: list[dict], required: list[str]) -> str | None:
    def ok(t: dict) -> bool:
        title = t["title"].lower()
        return all(w in title for w in required)
    candidates = [t for t in tables if ok(t)] or tables[:1]
    annual = [t for t in candidates if "annual" in t["frequency"].lower()]
    chosen = (annual or candidates)
    return chosen[0]["resource_id"] if chosen else None


def _pick_series(meta: dict, sectors: list[str]) -> list[str]:
    rows = meta.get("rows", [])
    chosen: list[str] = []
    for r in rows:
        text = (r.get("rowText") or "").lower()
        if sectors and any(s.lower() in text or text in s.lower() for s in sectors):
            chosen.append(str(r["seriesNo"]))
    if sectors and chosen:
        # include parents (e.g. "Services" for "Information And Communications") and top-level totals
        parents = {c.rsplit(".", 1)[0] for c in chosen if "." in c}
        chosen += [str(r["seriesNo"]) for r in rows if str(r["seriesNo"]) in parents]
        chosen += [str(r["seriesNo"]) for r in rows
                   if (r.get("rowText") or "").lower().startswith("total") and "." not in str(r["seriesNo"])]
    if not chosen:
        chosen = [str(r["seriesNo"]) for r in rows if "." not in str(r["seriesNo"])][:10]
    return sorted(set(chosen), key=lambda c: [int(p) if p.isdigit() else 0 for p in c.split(".")])


def extraction(ctx: RunContext, history: list[dict]) -> ReActStep:
    intent, plan_ = ctx.intent, ctx.plan
    for task in [t for t in plan_.tasks if t.agent == "extraction"]:
        q = task.query or ""
        if task.source == "singstat":
            search = _done(history, "singstat_search_tables", query_text=q)
            if search is None:
                return _step(f"{task.id}: search SingStat Table Builder via the MCP server for '{q}'.",
                             "singstat_search_tables", {"query_text": q})
            if "error" in search["observation"]:
                continue
            required = next((w for m, (sq, w) in SINGSTAT_SEARCH.items() if sq == q), q.split()[:2])
            rid = _pick_table(search["observation"].get("tables", []), required)
            if rid is None:
                continue
            meta = _done(history, "singstat_get_metadata", resource_id=rid)
            if meta is None:
                return _step(f"{task.id}: table {rid} looks right; read its metadata to find the series numbers.",
                             "singstat_get_metadata", {"resource_id": rid})
            if "error" in meta["observation"]:
                continue
            if _done(history, "fetch_singstat", resource_id=rid) is None:
                series = _pick_series(meta["observation"], intent.sectors)
                return _step(f"{task.id}: fetch series {', '.join(series[:8])} from {rid} for "
                             f"{intent.start_year}-{intent.end_year}.", "fetch_singstat",
                             {"resource_id": rid, "series": series})
        elif task.source == "datagov":
            search = _done(history, "datagov_search", query=q)
            if search is None:
                return _step(f"{task.id}: look for a Data.gov.sg CSV on '{q}'.", "datagov_search", {"query": q})
            hits = search["observation"].get("datasets", []) if "error" not in search["observation"] else []
            words = {w for w in q.lower().split() if len(w) > 3}
            hits = [h for h in hits if len(words & set(h["title"].lower().split())) >= min(2, len(words))]
            if hits and _done(history, "fetch_datagov", dataset_id=hits[0]["dataset_id"]) is None:
                return _step(f"{task.id}: download '{hits[0]['title']}' ({hits[0]['agency']}).", "fetch_datagov",
                             {"dataset_id": hits[0]["dataset_id"], "title": hits[0]["title"]})
        elif task.source == "mom":
            if _done(history, "fetch_mom_excel") is None:
                return _step(f"{task.id}: load the MOM Excel workbook to cross-check SingStat figures.",
                             "fetch_mom_excel", {})
        elif task.source == "internal":
            if _done(history, "query_internal_db", table="programme_enrolments") is None:
                return _step(f"{task.id}: query internal programme outcomes for the focus sectors.",
                             "query_internal_db", {"table": "programme_enrolments", "sectors": intent.sectors})
        elif task.source == "web":
            search = _done(history, "web_search", query=q)
            if search is None:
                return _step(f"{task.id}: search the web for qualitative context.", "web_search",
                             {"query": q, "max_results": 5})
            results = search["observation"].get("results", []) if "error" not in search["observation"] else []
            fetched = [h for h in history if h["action"] == "fetch_web_page"]
            ranked = sorted(results, key=lambda r: r.get("trust_tier", 3))
            if ranked and len(fetched) < 2:
                for r in ranked[:2]:
                    if _done(history, "fetch_web_page", url=r["url"]) is None:
                        return _step(f"{task.id}: read '{r['title'][:60]}' (trust tier {r.get('trust_tier')}).",
                                     "fetch_web_page", {"url": r["url"]})
    n = len(ctx.datasets)
    return _step("All planned extraction tasks are done.", "finish",
                 final=f"Collected {n} dataset(s): {', '.join(ctx.datasets)}. "
                       f"{len(ctx.context_notes)} web context note(s).")


# --- Analytics (ReAct) -----------------------------------------------------------------


FLOW_WORDS = ("retrench", "vacanc", "placement", "enrol", "hire", "hiring", "layoff")


# Metrics whose tables must be analysed in their own right (an employment table is no answer to them).
METRIC_TITLE_WORDS = {"retrench": "retrench", "vacanc": "vacanc", "unemploy": "unemploy", "compensation": "compensation"}


def _metric_word(ctx: RunContext) -> str | None:
    """Title keyword of the requested metric, if the run collected a table for it."""
    for metric in ctx.intent.metrics:
        for stem, word in METRIC_TITLE_WORDS.items():
            if stem in metric.lower() and any(word in r.title.lower() for r in ctx.datasets.values()):
                return word
    return None


def _targets(ctx: RunContext, annual_only: bool = True) -> tuple[list[str], list[str], str | None]:
    """(focus series refs, total refs, primary dataset key)."""
    intent = ctx.intent
    focus, totals, primary = [], [], None
    word = _metric_word(ctx)
    for key, rec in ctx.datasets.items():
        if rec.source_id not in ("singstat", "internal") or rec.frame is None or rec.frame.empty:
            continue
        if word and word not in rec.title.lower():
            continue
        if annual_only and rec.frame["frequency"].iloc[0] != "Annual":
            continue
        if not annual_only and (rec.frame["frequency"].iloc[0] == "Annual" or f"{key}~annual" in ctx.datasets):
            continue
        names = list(dict.fromkeys(rec.frame["series"].tolist()))
        for name in names:
            low = name.lower()
            if intent.sectors and any(s.lower() in low for s in intent.sectors):
                if rec.source_id == "internal" and "placed" not in low:
                    continue
                focus.append(f"{key}::{name}")
                primary = primary or key
            elif low.startswith("total") or low in ("services",):
                totals.append(f"{key}::{name}")
        if not intent.sectors:
            top = [n for n in names if "." not in str(rec.frame[rec.frame["series"] == n]["series_code"].iloc[0])]
            focus += [f"{key}::{n}" for n in top[:6]]
            primary = primary or key
    return focus[:6], totals, primary


def analytics(ctx: RunContext, history: list[dict]) -> ReActStep:
    intent = ctx.intent
    if _done(history, "list_series") is None:
        return _step("List the series the extraction agent collected.", "list_series", {})
    focus, totals, primary = _targets(ctx)
    if not focus:
        sub_annual, _, _ = _targets(ctx, annual_only=False)
        if sub_annual:
            flow = any(w in m.lower() for m in intent.metrics for w in FLOW_WORDS)
            how = "sum" if flow else "mean"
            return _step(f"Only {sub_annual[0].split('::')[0]} has the focus sector, at sub-annual frequency. "
                         f"Annualise it ({'flows are summed' if flow else 'levels are averaged'}) using "
                         f"complete years only.", "annualise", {"ref": sub_annual[0], "how": how})
        return _step("No annual series match the focus sectors; nothing to compute.", "finish",
                     final="No suitable series found for analysis.")
    main = focus[0]
    for tool in ("describe", "change", "cagr", "yoy", "trend"):
        for ref in focus[:3] if tool in ("cagr", "change") else [main]:
            if _done(history, tool, ref=ref) is None:
                return _step(f"Compute {tool} for {ref.split('::')[1]}.", tool, {"ref": ref})
    total_same = [t for t in totals if t.split("::")[0] == main.split("::")[0]]
    if total_same and _done(history, "share", ref=main) is None:
        return _step(f"Share of {main.split('::')[1]} in {total_same[0].split('::')[1]}.", "share",
                     {"ref": main, "total_ref": total_same[0]})
    if _done(history, "anomalies", ref=main) is None:
        return _step("Check for unusual years (e.g. the COVID-19 shock).", "anomalies", {"ref": main})
    others = [r for r in focus if r.split("::")[0] != main.split("::")[0]]
    if others and _done(history, "correlate", ref_a=main) is None:
        return _step(f"Two datasets overlap; test correlation with {others[0].split('::')[1]}.", "correlate",
                     {"ref_a": main, "ref_b": others[0]})
    if "forecast" in intent.analysis_types and _done(history, "forecast", ref=main) is None:
        return _step("The user asked for a forecast: project the trend 2 years ahead.", "forecast",
                     {"ref": main, "horizon": 2})
    charts = [h for h in history if h["action"] == "make_chart"]
    wanted = [("line", [r for r in focus if r.split("::")[0] == main.split("::")[0]][:4],
               f"{main.split('::')[1]}: levels, {intent.start_year}-{intent.end_year}"),
              ("indexed", [main] + total_same[:1] + [r for r in focus[1:3] if r != main],
               f"Indexed growth ({intent.start_year} = 100)"),
              ("yoy_bar", [main], f"Year-on-year growth: {main.split('::')[1]}")]
    if others:
        wanted.append(("scatter", [main, others[0]], f"{main.split('::')[1]} vs {others[0].split('::')[1]}"))
    if "forecast" in intent.analysis_types:
        wanted.append(("forecast", [main], f"Projection: {main.split('::')[1]}"))
    if len(charts) < len(wanted):
        kind, refs, title = wanted[len(charts)]
        return _step(f"Create a {kind} chart for the report.", "make_chart",
                     {"kind": kind, "refs": refs, "title": title})
    return _step("Analyses and charts are complete.", "finish",
                 final=f"Produced {len(ctx.facts)} facts and {len(ctx.charts)} charts.")


# --- Writer ----------------------------------------------------------------------------


def _fact(ctx: RunContext, method: str, ref_contains: str | None = None):
    for f in ctx.facts.values():
        if f.method == method and (ref_contains is None or ref_contains in f.key):
            return f
    return None


def write(ctx: RunContext, attempt: int, feedback: list[str]) -> ReportDraft:
    intent = ctx.intent
    focus, _, _ = _targets(ctx)
    main = focus[0] if focus else ""
    sector = main.split("::")[1] if main else "the selected series"
    # Say what is being measured when it is not employment, e.g. "Retrenchments in Information And ...".
    name = f"Retrenchments in {sector}" if main and _metric_word(ctx) == "retrench" else sector
    findings: list[Claim] = []

    def claim(text: str, *facts) -> None:
        facts = [f for f in facts if f is not None]
        if facts:
            findings.append(Claim(text=text, fact_ids=[f.id for f in facts],
                                  source_keys=sorted({k for f in facts for k in f.source_keys})))

    start_lv = _fact(ctx, "level", f"{main}:{intent.start_year}")
    end_lv = _fact(ctx, "level", f"{main}:{intent.end_year}") or next(
        (f for f in ctx.facts.values() if f.method == "level" and main in f.key and f is not start_lv), None)
    pct = _fact(ctx, "percent_change", main)
    cagr = _fact(ctx, "cagr", main)
    if start_lv and end_lv:
        claim(f"{name} moved from {start_lv.display} in {start_lv.params['period']} to {end_lv.display} in "
              f"{end_lv.params['period']}.", start_lv, end_lv)
    if pct and cagr:
        claim(f"That is a change of {pct.display} overall, or a compound annual growth rate of {cagr.display}.",
              pct, cagr)
    trend_r2 = _fact(ctx, "ols_r2", main)
    if trend_r2:
        claim(f"The trend is {'steady' if trend_r2.value >= 0.7 else 'uneven'} (R-squared of a linear fit: "
              f"{trend_r2.display}).", trend_r2)
    for f in [f for f in ctx.facts.values() if f.method == "zscore_anomaly" and main in f.key][:2]:
        claim(f"{f.params['period']} stands out, with year-on-year growth of {f.display}.", f)
    shares = sorted([f for f in ctx.facts.values() if f.method == "share" and main in f.key],
                    key=lambda f: f.params["period"])
    if len(shares) >= 2:
        claim(f"Its share of the wider total went from {shares[0].display} to {shares[-1].display}.",
              shares[0], shares[-1])
    for f in [f for f in ctx.facts.values() if f.method == "pearson"][:1]:
        claim(f"Across {f.params['window']} the correlation with the second series is {f.display} "
              f"(Pearson, n={f.params['n']}); correlation does not establish causation.", f)
    for f in [f for f in ctx.facts.values() if f.method == "linear_projection"]:
        claim(f"On a simple linear trend, {name} is projected at {f.display} in {f.params['year']} "
              "(projection, not an official forecast).", f)

    sector_claims: list[Claim] = []
    for f in [f for f in ctx.facts.values() if f.method == "cagr" and main not in f.key][:4]:
        sector_claims.append(Claim(text=f"{f.label.replace('CAGR of ', '')}: compound annual growth of {f.display}.",
                                   fact_ids=[f.id], source_keys=f.source_keys))

    if chaos.inject_hallucination and attempt == 1 and findings:
        bad = findings[0]
        findings[0] = Claim(text=bad.text + " This rose by 37.5% in the final year alone.",
                            fact_ids=bad.fact_ids, source_keys=bad.source_keys)

    implications = []
    if cagr and _metric_word(ctx) == "retrench":
        # For retrenchments a fall is good news, so the employment wording below would mislead.
        text = (f"Rising retrenchments in {sector} point to a need for job-matching and reskilling support for "
                "affected workers; monitor the next data release for confirmation." if cagr.value > 0 else
                f"Retrenchments in {sector} have eased over the period; confirm with the next data release "
                "before scaling back support for affected workers.")
        implications.append(Claim(text=text, fact_ids=[cagr.id], source_keys=cagr.source_keys))
    elif cagr:
        direction = "growth" if cagr.value > 0 else "contraction"
        implications.append(Claim(
            text=f"Sustained {direction} in {name} should inform workforce planning and training capacity for "
                 "the sector; monitor the next data release for confirmation.", fact_ids=[cagr.id],
            source_keys=cagr.source_keys))

    limitations = []
    for rec in ctx.datasets.values():
        if rec.is_fallback:
            limitations.append(f"{rec.title}: {rec.fallback_reason}")
        if rec.source_id == "internal":
            limitations.append("Internal programme data is synthetic (mock internal system).")
        if rec.quality:
            limitations += [f"{rec.title}: {i.message}" for i in rec.quality.issues if i.severity == "error"]
    limitations += ctx.warnings[:5]
    limitations += [f"LLM fallback: {f}" for f in ctx.fallbacks]
    limitations.append("Figures computed by this platform from official tables; derived values are not "
                       "attributed to DOS/MOM.")

    summary_bits = [c.text for c in findings[:2]]
    return ReportDraft(
        title=f"{intent.topic}",
        executive_summary=" ".join(summary_bits) or "Insufficient data to draw conclusions.",
        key_findings=findings,
        sector_analysis=sector_claims,
        policy_implications=implications,
        limitations=list(dict.fromkeys(limitations)),
    )
