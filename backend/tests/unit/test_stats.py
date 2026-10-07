"""Analytics functions against hand-computed values (the LLM never does arithmetic)."""

import pytest

from app.analytics import stats
from helpers import GROWTH, TOTAL, make_ctx, record

REF = "singstat:T1::Tech"


def ctx_growth():
    return make_ctx(record({"Tech": GROWTH, "Total": TOTAL}))


def by_method(facts, method):
    return [f for f in facts if f.method == method]


def test_describe_levels_and_peak():
    facts = stats.describe(ctx_growth(), REF)
    levels = {f.params["period"]: f.value for f in by_method(facts, "level")}
    assert levels == {"2020": 100.0, "2023": 133.1}
    peak = by_method(facts, "max")[0]
    assert peak.value == 133.1 and peak.params["period"] == "2023"
    assert all(not f.derived for f in facts)  # levels are copied from the source, not derived


def test_change_absolute_and_percent():
    facts = stats.change(ctx_growth(), REF)
    assert by_method(facts, "absolute_change")[0].value == pytest.approx(33.1)
    pct = by_method(facts, "percent_change")[0]
    assert pct.value == pytest.approx(33.1)
    assert pct.display == "33.1%"


def test_cagr_of_ten_percent_growth():
    fact = stats.cagr(ctx_growth(), REF)[0]
    assert fact.value == pytest.approx(10.0)
    assert fact.params["years"] == 3


def test_cagr_rejects_non_positive_values():
    ctx = make_ctx(record({"Tech": {"2020": 0.0, "2021": 5.0}}))
    with pytest.raises(stats.AnalyticsError):
        stats.cagr(ctx, REF)


def test_yoy_each_year_and_average():
    facts = stats.yoy(ctx_growth(), REF)
    yearly = by_method(facts, "yoy")
    assert [f.params["period"] for f in yearly] == ["2021", "2022", "2023"]
    assert all(f.value == pytest.approx(10.0) for f in yearly)
    assert by_method(facts, "yoy_mean")[0].value == pytest.approx(10.0)


def test_trend_slope_hand_computed():
    # x = 0..3, y = 100, 110, 121, 133.1 -> slope = sum((x - 1.5)(y - 116.025)) / 5 = 55.15 / 5
    facts = stats.trend(ctx_growth(), REF)
    assert by_method(facts, "ols_slope")[0].value == pytest.approx(11.03)
    assert 0.99 < by_method(facts, "ols_r2")[0].value <= 1.0


def test_share_of_total_at_window_ends():
    facts = stats.share(ctx_growth(), REF, "singstat:T1::Total")
    assert [round(f.value, 2) for f in facts] == [10.0, 13.31]
    assert facts[-1].display == "13.3%"


def test_window_restricts_periods():
    fact = stats.cagr(ctx_growth(), REF, "2021", "2022")[0]
    assert fact.value == pytest.approx(10.0)
    assert fact.params == {"from": "2021", "to": "2022", "years": 1.0}


def test_window_needs_two_points():
    with pytest.raises(stats.AnalyticsError):
        stats.change(ctx_growth(), REF, "2023", "2023")


def test_correlation_of_linear_transform_is_one():
    b = {p: 2 * v + 5 for p, v in GROWTH.items()}
    ctx = make_ctx(record({"Tech": GROWTH}), record({"Other": b}, key="internal:T2"))
    facts = stats.correlate(ctx, REF, "internal:T2::Other")
    assert by_method(facts, "pearson")[0].value == pytest.approx(1.0)
    assert by_method(facts, "spearman")[0].value == pytest.approx(1.0)
    assert by_method(facts, "pearson")[0].params["caveat"]  # n=4 is flagged as a small sample
    assert facts[0].source_keys == ["internal:T2", "singstat:T1"]


def test_correlation_needs_four_overlapping_periods():
    ctx = make_ctx(record({"Tech": {"2020": 1.0, "2021": 2.0, "2022": 3.0}}),
                   record({"Other": {"2020": 1.0, "2021": 2.0, "2022": 4.0}}, key="internal:T2"))
    with pytest.raises(stats.AnalyticsError):
        stats.correlate(ctx, REF, "internal:T2::Other")


def test_forecast_of_exact_line_has_zero_width_interval():
    ctx = make_ctx(record({"Tech": {"2019": 10.0, "2020": 20.0, "2021": 30.0, "2022": 40.0}}))
    facts = stats.forecast(ctx, REF, horizon=2)
    assert [f.params["year"] for f in facts] == [2023, 2024]
    assert [f.value for f in facts] == pytest.approx([50.0, 60.0])
    assert facts[0].params["lower"] == pytest.approx(facts[0].params["upper"])
    assert "projection" in facts[0].label


def test_anomaly_flags_the_outlier_year():
    values = {"2018": 100.0, "2019": 101.0, "2020": 102.0, "2021": 80.0, "2022": 81.0, "2023": 82.0}
    facts = stats.anomalies(make_ctx(record({"Tech": values})), REF)
    assert [f.params["period"] for f in facts] == ["2021"]


def test_annualise_sums_complete_years_only():
    quarters = {"2021-Q1": 1.0, "2021-Q2": 2.0, "2021-Q3": 3.0, "2021-Q4": 4.0,
                "2022-Q1": 5.0, "2022-Q2": 6.0, "2022-Q3": 7.0, "2022-Q4": 8.0,
                "2023-Q1": 9.0, "2023-Q2": 10.0}
    ctx = make_ctx(record({"Tech": quarters}, unit="Number", frequency="Quarterly"))
    out = stats.annualise(ctx, REF, "sum")
    assert out["ref"] == "singstat:T1~annual::Tech"
    assert out["years"] == ["2021", "2022"]
    assert out["incomplete_years_dropped"] == [2023]
    series, unit, key = stats.get_series(ctx, out["ref"])
    assert series.to_dict() == {"2021": 10.0, "2022": 26.0}
    assert key == "singstat:T1~annual" and unit == "Number"
    # The derived dataset is registered, so facts computed on it cite a dataset that exists.
    assert stats.change(ctx, out["ref"])[0].source_keys == ["singstat:T1~annual"]


def test_annualise_mean_for_levels():
    quarters = {f"2021-Q{q}": float(q) for q in range(1, 5)} | {f"2022-Q{q}": float(q + 4) for q in range(1, 5)}
    ctx = make_ctx(record({"Rate": quarters}, unit="%", frequency="Quarterly"))
    out = stats.annualise(ctx, "singstat:T1::Rate", "mean")
    series, _, _ = stats.get_series(ctx, out["ref"])
    assert series.to_dict() == {"2021": 2.5, "2022": 6.5}


def test_annualise_leaves_annual_series_alone():
    out = stats.annualise(ctx_growth(), REF)
    assert out["ref"] == REF


def test_unknown_series_reports_close_matches():
    with pytest.raises(stats.AnalyticsError, match="Similar"):
        stats.get_series(ctx_growth(), "singstat:T1::tech")


@pytest.mark.parametrize(("value", "unit", "expected"), [
    (157.6, "Thousand", "157.6 thousand"),
    (1910.0, "Number", "1,910"),
    (3.44, "%", "3.4%"),
    (0.55, "ratio", "0.55"),
])
def test_format_value(value, unit, expected):
    assert stats.format_value(value, unit) == expected
