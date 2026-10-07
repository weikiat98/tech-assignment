"""Anti-hallucination verifier: every number must come from a cited Fact, citations must exist,
years and sectors must be in the collected data."""

import pytest

from app.analytics import stats
from app.core.models import Claim, ReportDraft
from app.verification.checks import check_claim, drop_failing, extract_numbers, verify
from helpers import make_ctx, record

SECTOR = "Information And Communications"
REF = f"singstat:T1::{SECTOR}"


@pytest.fixture
def ctx():
    c = make_ctx(record({SECTOR: {"2020": 157.6, "2021": 172.9, "2022": 187.5, "2023": 182.3, "2024": 180.3}}))
    stats.describe(c, REF)
    stats.change(c, REF)
    stats.cagr(c, REF)
    return c


def fact(ctx, method, period=None):
    return next(f for f in ctx.facts.values() if f.method == method
                and (period is None or f.params.get("period") == period))


def claim_for(ctx, text, *facts):
    return Claim(text=text, fact_ids=[f.id for f in facts])


def test_correct_claim_passes(ctx):
    start, end = fact(ctx, "level", "2020"), fact(ctx, "level", "2024")
    check = check_claim(claim_for(ctx, f"{SECTOR} moved from 157.6 thousand in 2020 to 180.3 thousand in 2024.",
                                  start, end), "key_findings", ctx)
    assert check.passed, check.problems


def test_injected_wrong_number_fails(ctx):
    start = fact(ctx, "level", "2020")
    check = check_claim(claim_for(ctx, f"{SECTOR} rose by 37.5% in the final year from 157.6 thousand.", start),
                        "key_findings", ctx)
    assert not check.passed
    assert any("37.5" in p for p in check.problems)


def test_number_from_an_uncited_fact_fails(ctx):
    # 14.4% exists as a fact, but this claim cites only the 2020 level.
    check = check_claim(claim_for(ctx, "Employment grew 14.4%.", fact(ctx, "level", "2020")), "key_findings", ctx)
    assert not check.passed


def test_numeric_claim_without_citation_fails(ctx):
    check = check_claim(Claim(text="Employment grew 14.4%."), "key_findings", ctx)
    assert "numeric claim without a fact citation" in check.problems


def test_executive_summary_may_use_any_fact(ctx):
    check = check_claim(Claim(text="Employment grew 14.4% (3.4% a year)."), "executive_summary", ctx, all_facts=True)
    assert check.passed, check.problems


def test_rounding_within_display_precision(ctx):
    pct = fact(ctx, "percent_change")
    assert check_claim(claim_for(ctx, "A change of 14.4%.", pct), "k", ctx).passed
    assert not check_claim(claim_for(ctx, "A change of 14.6%.", pct), "k", ctx).passed


def test_unknown_fact_id_and_source_fail(ctx):
    check = check_claim(Claim(text="Steady.", fact_ids=["F99"], source_keys=["datagov:nope"]), "k", ctx)
    assert any("unknown fact ids" in p for p in check.problems)
    assert any("unknown sources" in p for p in check.problems)


def test_year_outside_data_range_fails(ctx):
    check = check_claim(Claim(text="The trend started in 1995."), "k", ctx)
    assert any("year 1995" in p for p in check.problems)


def test_thousands_separated_count_is_not_a_year():
    c = make_ctx(record({SECTOR: {"2023": 2610.0, "2025": 1910.0}}, unit="Number"))
    stats.describe(c, REF)
    end = fact(c, "level", "2025")
    check = check_claim(claim_for(c, f"{SECTOR} retrenchments fell to 1,910 in 2025.", end), "k", c)
    assert check.passed, check.problems


def test_sector_not_in_data_fails(ctx):
    check = check_claim(Claim(text="Construction also grew."), "k", ctx)
    assert any("Construction" in p for p in check.problems)


def test_right_numbers_wrong_sector_fails():
    """Numbers match the cited ICT facts, but the claim attributes them to another sector."""
    c = make_ctx(record({SECTOR: {"2020": 157.6, "2024": 180.3}, "Construction": {"2020": 400.0, "2024": 420.0}}))
    stats.describe(c, REF)
    start, end = fact(c, "level", "2020"), fact(c, "level", "2024")
    honest = claim_for(c, f"{SECTOR} moved from 157.6 thousand in 2020 to 180.3 thousand in 2024.", start, end)
    swapped = claim_for(c, "Construction moved from 157.6 thousand in 2020 to 180.3 thousand in 2024.", start, end)
    assert check_claim(honest, "k", c).passed
    problems = check_claim(swapped, "k", c).problems
    assert any("not what the cited facts measure" in p for p in problems)


def test_verify_rates_and_drop_failing(ctx):
    good = claim_for(ctx, "A change of 14.4%.", fact(ctx, "percent_change"))
    bad = claim_for(ctx, "A change of 99.9%.", fact(ctx, "percent_change"))
    draft = ReportDraft(title="t", executive_summary="Employment grew 14.4%.", key_findings=[good, bad])
    result = verify(draft, ctx, attempt=1)
    assert not result.passed
    assert result.numeric_pass_rate == pytest.approx(2 / 3, abs=1e-3)
    assert good.source_keys == ["singstat:T1"]  # back-filled from the cited fact
    cleaned = drop_failing(draft, result)
    assert [c.text for c in cleaned.key_findings] == ["A change of 14.4%."]
    assert "1 claim(s) removed" in cleaned.limitations[-1]


def test_extract_numbers_handles_signs_percent_and_grouping():
    assert extract_numbers("fell -26.8% to 1,910 from 2,610.5 in 2023") == [
        (-26.8, 1, True), (1910.0, 0, False), (2610.5, 1, False), (2023.0, 0, False)]
