"""Deterministic hallucination checks on the drafted report (plan.md §10.2, layers 2-4).

1. Numeric: every number in a claim must match a cited Fact (value, display or parameter)
   within display rounding. Executive-summary numbers must match some Fact.
2. Citations: cited fact ids and source keys must exist in this run; numeric claims need a fact.
3. Entities: years must fall inside the data range (+ projection horizon); named sectors must
   exist in the collected data.
"""

from __future__ import annotations

import re

from app.agents.vocab import ALL_SECTOR_NAMES, SECTOR_KEYWORDS
from app.core.models import Claim, ClaimCheck, Fact, ReportDraft, VerificationResult
from app.core.run_context import RunContext

_NUMBER = re.compile(r"(?<![\w.])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|(?<![\w.])[-+]?\d+(?:\.\d+)?%?")


def extract_numbers(text: str) -> list[tuple[float, int, bool]]:
    """(value, decimals, is_percent) for each number token."""
    return [(value, decimals, pct) for value, decimals, pct, _ in extract_number_tokens(text)]


def extract_number_tokens(text: str) -> list[tuple[float, int, bool, str]]:
    """(value, decimals, is_percent, raw token) for each number token."""
    out = []
    for token in _NUMBER.findall(text):
        pct = token.endswith("%")
        raw = token.rstrip("%").replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        out.append((value, decimals, pct, token))
    return out


def _is_year(value: float, decimals: int, pct: bool, token: str = "") -> bool:
    # "1,910" is a count, not a year: years are never written with a thousands separator.
    return not pct and decimals == 0 and "," not in token and 1900 <= value <= 2100


def _allowed(facts: list[Fact]) -> list[float]:
    vals: list[float] = []
    for f in facts:
        vals += [f.value, abs(f.value), f.value * 100]
        vals += [v for v, _, _ in extract_numbers(f.display)]
        vals += [float(v) for v in f.params.values() if isinstance(v, int | float)]
        for v in f.params.values():
            if isinstance(v, str):
                vals += [n for n, _, _ in extract_numbers(v)]
    return vals


def _matches(value: float, decimals: int, allowed: list[float]) -> bool:
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    return any(abs(abs(value) - abs(a)) <= tol for a in allowed)


def _year_bounds(ctx: RunContext) -> tuple[int, int]:
    years = []
    for rec in ctx.datasets.values():
        if rec.frame is not None and not rec.frame.empty:
            years += [int(str(p)[:4]) for p in rec.frame["period"].unique()]
    if not years:
        return 1900, 2100
    return min(years), max(years) + 3  # allow projection horizon


def _known_sectors(ctx: RunContext) -> set[str]:
    present = set()
    for rec in ctx.datasets.values():
        if rec.frame is None or rec.frame.empty:
            continue
        names = " | ".join(rec.frame["series"].unique()).lower()
        for sector in ALL_SECTOR_NAMES:
            if sector.lower() in names:
                present.add(sector)
    return present


def check_claim(claim: Claim, section: str, ctx: RunContext, all_facts: bool = False) -> ClaimCheck:
    problems: list[str] = []
    cited = [ctx.facts[i] for i in claim.fact_ids if i in ctx.facts]
    missing = [i for i in claim.fact_ids if i not in ctx.facts]
    if missing:
        problems.append(f"cites unknown fact ids {missing}")
    bad_sources = [k for k in claim.source_keys if k not in ctx.datasets]
    if bad_sources:
        problems.append(f"cites unknown sources {bad_sources}")

    numbers = extract_number_tokens(claim.text)
    lo, hi = _year_bounds(ctx)
    pool = list(ctx.facts.values()) if all_facts else cited
    allowed = _allowed(pool)
    numeric_claim = False
    for value, decimals, pct, token in numbers:
        if _is_year(value, decimals, pct, token):
            if not lo <= value <= hi:
                problems.append(f"year {int(value)} outside the data range {lo}-{hi}")
            continue
        numeric_claim = True
        if not _matches(value, decimals, allowed):
            problems.append(f"number {value:g}{'%' if pct else ''} not supported by "
                            f"{'any fact' if all_facts else 'the cited facts'}")
    if numeric_claim and not cited and not all_facts:
        problems.append("numeric claim without a fact citation")

    present = _known_sectors(ctx)
    low = claim.text.lower()
    cited_labels = " | ".join(f.label for f in cited).lower()
    for sector in ALL_SECTOR_NAMES:
        if sector.lower() not in low:
            continue
        if sector not in present:
            problems.append(f"sector '{sector}' is not in the collected data")
        elif cited and numeric_claim and sector.lower() not in cited_labels:
            # Right numbers, wrong subject: "Construction grew 14.4%" citing an ICT fact.
            problems.append(f"sector '{sector}' is not what the cited facts measure")
    return ClaimCheck(claim=claim.text, section=section, passed=not problems, problems=problems)


def verify(draft: ReportDraft, ctx: RunContext, attempt: int) -> VerificationResult:
    checks: list[ClaimCheck] = [check_claim(Claim(text=draft.executive_summary), "executive_summary", ctx,
                                            all_facts=True)]
    for section in ("key_findings", "sector_analysis", "policy_implications"):
        for claim in getattr(draft, section):
            # Back-fill source keys from cited facts so citations are always complete.
            if not claim.source_keys:
                claim.source_keys = sorted({k for i in claim.fact_ids if i in ctx.facts
                                            for k in ctx.facts[i].source_keys})
            checks.append(check_claim(claim, section, ctx))

    def rate(kind: str) -> float:
        relevant = [c for c in checks if any(kind in p for p in c.problems)]
        return 1 - len(relevant) / max(len(checks), 1)

    return VerificationResult(
        passed=all(c.passed for c in checks), checks=checks,
        numeric_pass_rate=round(rate("number"), 3),
        citation_pass_rate=round(min(rate("cites"), rate("citation")), 3),
        entity_pass_rate=round(min(rate("year"), rate("sector")), 3), attempt=attempt,
    )


def drop_failing(draft: ReportDraft, result: VerificationResult) -> ReportDraft:
    """After the rewrite budget is spent, remove claims that still fail (never publish them)."""
    failing = {c.claim for c in result.checks if not c.passed}
    for section in ("key_findings", "sector_analysis", "policy_implications"):
        setattr(draft, section, [c for c in getattr(draft, section) if c.text not in failing])
    if draft.executive_summary in failing:
        draft.executive_summary = " ".join(c.text for c in draft.key_findings[:2]) or draft.executive_summary
    draft.limitations.append(f"{len(failing)} claim(s) removed by the verifier after failed rewrites.")
    return draft


SECTOR_HINT = ", ".join(SECTOR_KEYWORDS)
