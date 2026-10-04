"""Data-quality validation and cleaning for canonical frames (plan.md §5.2).

Checks are plain pandas so every rule is explicit, testable and explained in the UI.
"""

from __future__ import annotations

import pandas as pd

from app.core.models import CANONICAL_COLUMNS, DatasetRecord, QualityIssue, QualityReport

PENALTY = {"info": 0.0, "warning": 0.07, "error": 0.25}
ROUNDING_TOLERANCE = 0.02  # parent vs sum(children): "may not add up due to rounding"


def clean(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    actions: list[str] = []
    df = frame.copy()
    df["series"] = df["series"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    before = len(df)
    df = df.drop_duplicates(subset=["series", "period"], keep="last")
    if len(df) < before:
        actions.append(f"Removed {before - len(df)} duplicate series/period rows")
    # Interpolate only isolated single gaps inside a series; never extrapolate or fill runs.
    filled = 0
    parts = []
    for _, g in df.sort_values("period_start").groupby("series", sort=False):
        values = g["value"].astype(float)
        isolated = values.isna() & values.shift(1).notna() & values.shift(-1).notna()
        if isolated.any():
            interp = values.interpolate(limit=1, limit_area="inside")
            g = g.assign(value=values.where(~isolated, interp))
            filled += int(isolated.sum())
        parts.append(g)
    if parts:
        df = pd.concat(parts)
    if filled:
        actions.append(f"Interpolated {filled} isolated missing value(s) (linear, single gaps only)")
    remaining = int(df["value"].isna().sum())
    if remaining:
        df = df[df["value"].notna()]
        actions.append(f"Excluded {remaining} missing value(s) that could not be safely filled")
    return df.reset_index(drop=True), actions


def check(record: DatasetRecord, start_year: int | None = None, end_year: int | None = None) -> QualityReport:
    df: pd.DataFrame = record.frame
    issues: list[QualityIssue] = []

    missing_cols = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing_cols:
        issues.append(QualityIssue(check="schema", severity="error", message=f"Missing columns: {missing_cols}"))
    if df.empty:
        issues.append(QualityIssue(check="completeness", severity="error", message="Dataset has no rows"))
        return QualityReport(dataset_key=record.key, score=0.0, row_count=0, issues=issues)

    null_ratio = float(df["value"].isna().mean())
    if null_ratio > 0:
        sev = "warning" if null_ratio < 0.2 else "error"
        issues.append(QualityIssue(check="completeness", severity=sev,
                                   message=f"{null_ratio:.0%} of values are missing"))

    dups = int(df.duplicated(subset=["series", "period"]).sum())
    if dups:
        issues.append(QualityIssue(check="consistency", severity="warning",
                                   message=f"{dups} duplicate series/period rows"))

    numeric = df["value"].dropna()
    pct_mask = df["unit"].astype(str).str.contains("%|per cent|percent", case=False, regex=True)
    if pct_mask.any() and ((df.loc[pct_mask, "value"] < -100) | (df.loc[pct_mask, "value"] > 100)).any():
        issues.append(QualityIssue(check="validity", severity="error", message="Percentage outside [-100, 100]"))
    count_mask = df["unit"].astype(str).str.contains("number|persons|thousand", case=False, regex=True)
    if count_mask.any() and (df.loc[count_mask, "value"] < 0).any():
        issues.append(QualityIssue(check="validity", severity="error", message="Negative values in a count series"))
    if numeric.empty:
        issues.append(QualityIssue(check="validity", severity="error", message="No numeric values"))

    # Requested range coverage (annual granularity).
    if start_year or end_year:
        years = pd.to_datetime(df["period_start"]).dt.year
        present = set(years.unique().tolist())
        wanted = set(range(start_year or min(present), (end_year or max(present)) + 1))
        missing_years = sorted(wanted - present)
        if missing_years:
            sev = "warning" if len(missing_years) < len(wanted) else "error"
            issues.append(QualityIssue(check="timeliness", severity=sev,
                                       message=f"Requested years not available: {missing_years}"))

    # Hierarchical consistency (SingStat series codes like 3 -> 3.1, 3.2 ...).
    issues.extend(_hierarchy_issues(df))

    if record.is_fallback:
        issues.append(QualityIssue(check="provenance", severity="warning",
                                   message=f"Served from fallback: {record.fallback_reason}"))
    if record.footnote:
        issues.append(QualityIssue(check="caveat", severity="info", message=f"Source footnote: {record.footnote}"))

    score = max(0.0, 1.0 - sum(PENALTY[i.severity] for i in issues))
    return QualityReport(dataset_key=record.key, score=round(score, 2), row_count=int(len(df)), issues=issues)


def _hierarchy_issues(df: pd.DataFrame) -> list[QualityIssue]:
    codes = df[["series", "series_code"]].drop_duplicates()
    codes = codes[codes["series_code"].astype(str).str.match(r"^\d+(\.\d+)*$")]
    if codes.empty:
        return []
    issues = []
    code_set = set(codes["series_code"])
    for parent in code_set:
        children = sorted(c for c in code_set if c.startswith(parent + ".") and c.count(".") == parent.count(".") + 1)
        if len(children) < 2:
            continue
        pivot = df[df["series_code"].isin([parent, *children])].pivot_table(
            index="period", columns="series_code", values="value", aggfunc="first")
        if parent not in pivot:
            continue
        child_sum = pivot[[c for c in children if c in pivot]].sum(axis=1, min_count=1)
        rel_gap = ((pivot[parent] - child_sum).abs() / pivot[parent].abs()).dropna()
        worst = rel_gap.max() if not rel_gap.empty else 0
        if worst > ROUNDING_TOLERANCE:
            issues.append(QualityIssue(
                check="consistency", severity="info",
                message=(f"Series {parent}: children sum differs from total by up to {worst:.1%} "
                         "(source lists only selected sub-sectors, or rounding)")))
    return issues


def process(record: DatasetRecord, start_year: int | None, end_year: int | None) -> DatasetRecord:
    """Check -> clean -> attach report (actions recorded so the UI can show what changed)."""
    report = check(record, start_year, end_year)
    cleaned, actions = clean(record.frame) if not record.frame.empty else (record.frame, [])
    report.actions = actions
    record.frame = cleaned
    record.quality = report
    return record
