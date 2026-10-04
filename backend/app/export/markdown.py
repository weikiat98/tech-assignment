"""Render the structured report (from the result JSON) as Markdown with citations."""

from __future__ import annotations

from typing import Any


def _claims(claims: list[dict[str, Any]]) -> str:
    lines = []
    for c in claims:
        cites = " ".join(f"[{f}]" for f in c.get("fact_ids", []))
        lines.append(f"- {c['text']} {cites}".rstrip())
    return "\n".join(lines)


def render(result: dict[str, Any]) -> str:
    report = result.get("report") or {}
    verification = result.get("verification") or {}
    out = [f"# {report.get('title', 'Analysis report')}", ""]
    out.append(f"*Query:* {result.get('query', '')}  ")
    status = "passed" if verification.get("passed") else "issues found"
    out.append(f"*Verification:* {status} (numeric {verification.get('numeric_pass_rate', 0):.0%}, "
               f"citations {verification.get('citation_pass_rate', 0):.0%}, "
               f"entities {verification.get('entity_pass_rate', 0):.0%})")
    out += ["", "## Executive summary", "", report.get("executive_summary", ""), ""]
    for title, key in (("Key findings", "key_findings"), ("Sector analysis", "sector_analysis"),
                       ("Policy implications", "policy_implications")):
        if report.get(key):
            out += [f"## {title}", "", _claims(report[key]), ""]
    notes = result.get("context_notes") or []
    if notes:
        out += ["## Context from the web", ""]
        for n in notes:
            flag = " (suspected prompt-injection text removed)" if n.get("injection_flagged") else ""
            out.append(f"- Reported by [{n['title']}]({n['url']}) (trust tier {n['trust_tier']}){flag}: "
                       f"\"{n['excerpt'][:300]}\"")
        out.append("")
    if report.get("limitations"):
        out += ["## Limitations", ""] + [f"- {item}" for item in report["limitations"]] + [""]
    out += ["## Facts", "", "| Id | Fact | Value | Method | Sources |", "|---|---|---|---|---|"]
    for f in result.get("facts", []):
        out.append(f"| {f['id']} | {f['label']} | {f['display']} | {f['method']} | {', '.join(f['source_keys'])} |")
    out += ["", "## Data sources", ""]
    for d in result.get("datasets", []):
        fallback = f" - fallback: {d['fallback_reason']}" if d.get("is_fallback") else ""
        agency = f", {d['agency']}" if d.get("agency") else ""
        out.append(f"- **{d['key']}** - {d['title']}{agency}. {d.get('url') or ''} "
                   f"(retrieved {d['retrieved_at'][:10]}, quality {((d.get('quality') or {}).get('score') or 0):.2f})"
                   f"{fallback}")
    out += ["", "_Derived values (growth rates, shares, correlations, projections) are computed by this platform "
                "from the cited tables and are not attributed to the source agencies._"]
    return "\n".join(out)
