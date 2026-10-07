"""Data-quality checks and cleaning on deliberately defective fixtures."""

import pandas as pd

from app.quality.checks import check, clean, process
from helpers import frame, record


def issues(report, check_name=None):
    return [i for i in report.issues if check_name is None or i.check == check_name]


def test_clean_dataset_scores_full_marks():
    report = check(record({"Tech": {"2020": 1.0, "2021": 2.0, "2022": 3.0}}), 2020, 2022)
    assert report.score == 1.0 and report.issues == []


def test_duplicates_flagged_then_removed():
    rec = record({"Tech": {"2020": 1.0, "2021": 2.0}})
    rec.frame = pd.concat([rec.frame, rec.frame.iloc[[1]]], ignore_index=True)
    assert issues(check(rec), "consistency")
    cleaned, actions = clean(rec.frame)
    assert len(cleaned) == 2 and "Removed 1 duplicate" in actions[0]


def test_isolated_gap_interpolated_but_runs_excluded():
    df = frame({"A": {"2019": 10.0, "2020": None, "2021": 30.0},
                "B": {"2019": 1.0, "2020": None, "2021": None, "2022": 4.0}})
    cleaned, actions = clean(df)
    a = cleaned[cleaned["series"] == "A"].set_index("period")["value"]
    assert a["2020"] == 20.0
    assert set(cleaned[cleaned["series"] == "B"]["period"]) == {"2019", "2022"}  # a 2-year run is never invented
    assert any("Interpolated 1" in x for x in actions) and any("Excluded 2" in x for x in actions)


def test_missing_values_severity_scales():
    few = record({"A": {str(y): (None if y == 2015 else 1.0) for y in range(2010, 2020)}})
    many = record({"A": {"2020": None, "2021": None, "2022": 1.0}})
    assert issues(check(few), "completeness")[0].severity == "warning"
    assert issues(check(many), "completeness")[0].severity == "error"


def test_negative_counts_and_impossible_percentages_are_errors():
    counts = check(record({"A": {"2020": -5.0, "2021": 3.0}}, unit="Number"))
    pct = check(record({"A": {"2020": 150.0, "2021": 3.0}}, unit="%"))
    assert issues(counts, "validity")[0].message == "Negative values in a count series"
    assert issues(pct, "validity")[0].message == "Percentage outside [-100, 100]"
    assert counts.score == 0.75


def test_requested_years_missing():
    report = check(record({"A": {"2020": 1.0, "2021": 2.0}}), 2019, 2022)
    assert "[2019, 2022]" in issues(report, "timeliness")[0].message


def test_hierarchy_mismatch_reported_as_info():
    df = frame({"Total": {"2020": 100.0}, "Part A": {"2020": 40.0}, "Part B": {"2020": 30.0}},
               codes={"Total": "1", "Part A": "1.1", "Part B": "1.2"})
    rec = record({"x": {"2020": 1.0}})
    rec.frame = df
    hierarchy = [i for i in check(rec).issues if "children sum" in i.message]
    assert hierarchy and hierarchy[0].severity == "info"


def test_fallback_provenance_lowers_score():
    rec = record({"A": {"2020": 1.0, "2021": 2.0}})
    rec.is_fallback, rec.fallback_reason = True, "served via snapshot"
    report = check(rec)
    assert issues(report, "provenance") and report.score < 1.0


def test_process_attaches_report_and_actions():
    rec = process(record({"A": {"2019": 1.0, "2020": None, "2021": 3.0}}), 2019, 2021)
    assert rec.quality is not None and rec.quality.actions
    assert rec.frame["value"].notna().all()
