"""Deterministic analytics. Every result is returned as Facts; the LLM never does arithmetic.

Series are referenced as "<dataset_key>::<series name>", e.g.
"singstat:M182841::Information And Communications".
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from app.core.models import Fact
from app.core.run_context import RunContext


class AnalyticsError(ValueError):
    pass


def format_value(value: float, unit: str) -> str:
    u = (unit or "").lower()
    if u in ("%", "percent", "per cent", "pp"):
        return f"{value:.1f}%" if u != "pp" else f"{value:.1f} percentage points"
    if u == "thousand":
        return f"{value:,.1f} thousand"
    if u in ("number", "persons", "") and float(value).is_integer():
        return f"{value:,.0f}"
    if u in ("r", "ratio", "coefficient"):
        return f"{value:.2f}"
    if "million" in u:
        return f"{value:,.1f} {unit}"
    return f"{value:,.2f} {unit}".strip()


def split_ref(ref: str) -> tuple[str, str]:
    if "::" not in ref:
        raise AnalyticsError(f"Series reference '{ref}' must look like '<dataset_key>::<series>'")
    dataset_key, series = ref.split("::", 1)
    return dataset_key, series


def get_series(ctx: RunContext, ref: str) -> tuple[pd.Series, str, str]:
    """Return (values indexed by period label, unit, dataset_key)."""
    dataset_key, name = split_ref(ref)
    record = ctx.datasets.get(dataset_key)
    if record is None:
        raise AnalyticsError(f"Unknown dataset '{dataset_key}'. Known: {list(ctx.datasets)}")
    df = record.frame
    rows = df[df["series"] == name]
    if rows.empty:
        close = [s for s in df["series"].unique() if name.lower() in s.lower()]
        raise AnalyticsError(f"Series '{name}' not in {dataset_key}. Similar: {close[:5]}")
    rows = rows.sort_values("period_start")
    series = pd.Series(rows["value"].astype(float).values, index=rows["period"].values).dropna()
    unit = str(rows["unit"].mode().iloc[0]) if not rows["unit"].empty else ""
    return series, unit, dataset_key


def list_series(ctx: RunContext) -> list[dict]:
    out = []
    for key, rec in ctx.datasets.items():
        if rec.frame is None or rec.frame.empty:
            continue
        for name, g in rec.frame.groupby("series"):
            out.append({"ref": f"{key}::{name}", "unit": str(g["unit"].iloc[0]), "periods":
                        [str(g["period"].min()), str(g["period"].max())], "n": int(g["value"].notna().sum()),
                        "frequency": str(g["frequency"].iloc[0])})
    return out


PERIODS_PER_YEAR = {"Quarterly": 4, "Monthly": 12, "Half-Yearly": 2}
ANNUAL_SUFFIX = "~annual"


def annualise(ctx: RunContext, ref: str, how: str = "sum") -> dict:
    """Turn a quarterly/monthly series into an annual one and register it as a derived dataset.

    Only complete years are kept (4 quarters / 12 months), so a partial latest year never looks
    like a fall. ``sum`` suits flows (retrenchments, vacancies created); ``mean`` suits stocks and
    rates. The derived dataset key is ``<dataset_key>~annual`` so every fact stays traceable to
    the official table it came from.
    """
    if how not in ("sum", "mean"):
        raise AnalyticsError("how must be 'sum' (flows) or 'mean' (stocks and rates)")
    dataset_key, name = split_ref(ref)
    record = ctx.datasets.get(dataset_key)
    if record is None:
        raise AnalyticsError(f"Unknown dataset '{dataset_key}'. Known: {list(ctx.datasets)}")
    rows = record.frame[record.frame["series"] == name].dropna(subset=["value"])
    if rows.empty:
        raise AnalyticsError(f"Series '{name}' not in {dataset_key}")
    freq = str(rows["frequency"].iloc[0])
    if freq == "Annual":
        return {"ref": ref, "how": "unchanged (already annual)", "years": sorted(rows["period"].astype(str))}
    per_year = PERIODS_PER_YEAR.get(freq)
    if per_year is None:
        raise AnalyticsError(f"Cannot annualise {freq} data")
    years = pd.to_datetime(rows["period_start"]).dt.year
    grouped = rows.assign(year=years.values).groupby("year")["value"].agg([how, "count"])
    complete = grouped[grouped["count"] == per_year]
    if len(complete) < 2:
        raise AnalyticsError(f"Fewer than 2 complete years of {freq.lower()} data for '{name}'")
    first = rows.iloc[0]
    derived = pd.DataFrame({
        "source_id": first["source_id"], "dataset_id": first["dataset_id"], "series": name,
        "series_code": first["series_code"], "period": [str(y) for y in complete.index],
        "period_start": [pd.Timestamp(year=int(y), month=1, day=1).date() for y in complete.index],
        "frequency": "Annual", "value": complete[how].astype(float).values, "unit": first["unit"],
    })
    new_key = dataset_key + ANNUAL_SUFFIX
    existing = ctx.datasets.get(new_key)
    if existing is not None:
        frame = pd.concat([existing.frame[existing.frame["series"] != name], derived], ignore_index=True)
        existing.frame = frame
    else:
        note = (f"Annual {'totals' if how == 'sum' else 'averages'} of {freq.lower()} values from "
                f"{dataset_key}, complete years only (derived by this platform).")
        ctx.add_dataset(record.model_copy(update={
            "key": new_key, "title": f"{record.title} (annualised)", "frequency": "Annual",
            "frame": derived, "notes": [*record.notes, note]}))
    dropped = sorted(int(y) for y in grouped.index if y not in complete.index)
    return {"ref": f"{new_key}::{name}", "how": how, "years": [str(y) for y in complete.index],
            "incomplete_years_dropped": dropped}


def _window(series: pd.Series, start: str | None, end: str | None) -> pd.Series:
    s = series
    if start:
        s = s[s.index >= str(start)]
    if end:
        s = s[s.index <= str(end) + "~"]  # "~" sorts after quarter/month suffixes
    if len(s) < 2:
        raise AnalyticsError(f"Need at least 2 data points in window {start}-{end}, got {len(s)}")
    return s


def _short(ref: str) -> str:
    return split_ref(ref)[1]


def describe(ctx: RunContext, ref: str, start: str | None = None, end: str | None = None) -> list[Fact]:
    s, unit, key = get_series(ctx, ref)
    s = _window(s, start, end)
    name = _short(ref)
    facts = [
        Fact(key=f"level:{ref}:{s.index[-1]}", label=f"{name} in {s.index[-1]}", value=float(s.iloc[-1]),
             unit=unit, display=format_value(float(s.iloc[-1]), unit), method="level",
             params={"period": s.index[-1]}, source_keys=[key], derived=False),
        Fact(key=f"level:{ref}:{s.index[0]}", label=f"{name} in {s.index[0]}", value=float(s.iloc[0]),
             unit=unit, display=format_value(float(s.iloc[0]), unit), method="level",
             params={"period": s.index[0]}, source_keys=[key], derived=False),
        Fact(key=f"max:{ref}:{s.index[0]}-{s.index[-1]}", label=f"{name} peak ({s.idxmax()})",
             value=float(s.max()), unit=unit, display=format_value(float(s.max()), unit), method="max",
             params={"period": s.idxmax(), "window": [s.index[0], s.index[-1]]}, source_keys=[key], derived=False),
    ]
    return [ctx.add_fact(f) for f in facts]


def change(ctx: RunContext, ref: str, start: str | None = None, end: str | None = None) -> list[Fact]:
    s, unit, key = get_series(ctx, ref)
    s = _window(s, start, end)
    name, a, b = _short(ref), float(s.iloc[0]), float(s.iloc[-1])
    facts = [Fact(key=f"abs_change:{ref}:{s.index[0]}-{s.index[-1]}",
                  label=f"Change in {name}, {s.index[0]}-{s.index[-1]}", value=b - a, unit=unit,
                  display=format_value(b - a, unit), method="absolute_change",
                  params={"from": s.index[0], "to": s.index[-1]}, source_keys=[key])]
    if a != 0:
        pct = (b - a) / abs(a) * 100
        facts.append(Fact(key=f"pct_change:{ref}:{s.index[0]}-{s.index[-1]}",
                          label=f"% change in {name}, {s.index[0]}-{s.index[-1]}", value=pct, unit="%",
                          display=format_value(pct, "%"), method="percent_change",
                          params={"from": s.index[0], "to": s.index[-1]}, source_keys=[key]))
    return [ctx.add_fact(f) for f in facts]


def cagr(ctx: RunContext, ref: str, start: str | None = None, end: str | None = None) -> list[Fact]:
    s, unit, key = get_series(ctx, ref)
    s = _window(s, start, end)
    a, b = float(s.iloc[0]), float(s.iloc[-1])
    periods = len(s) - 1
    if a <= 0 or b <= 0:
        raise AnalyticsError("CAGR needs positive start and end values")
    freq_per_year = 4 if "-Q" in str(s.index[0]) else (12 if len(str(s.index[0])) == 7 else 1)
    years = periods / freq_per_year
    value = ((b / a) ** (1 / years) - 1) * 100
    fact = Fact(key=f"cagr:{ref}:{s.index[0]}-{s.index[-1]}",
                label=f"CAGR of {_short(ref)}, {s.index[0]}-{s.index[-1]}", value=value, unit="%",
                display=format_value(value, "%"), method="cagr",
                params={"from": s.index[0], "to": s.index[-1], "years": years}, source_keys=[key])
    return [ctx.add_fact(fact)]


def yoy(ctx: RunContext, ref: str, start: str | None = None, end: str | None = None) -> list[Fact]:
    s, unit, key = get_series(ctx, ref)
    s = _window(s, start, end)
    lag = 4 if "-Q" in str(s.index[0]) else (12 if len(str(s.index[0])) == 7 else 1)
    growth = (s / s.shift(lag) - 1) * 100
    facts = []
    for period, value in growth.dropna().items():
        facts.append(Fact(key=f"yoy:{ref}:{period}", label=f"YoY growth of {_short(ref)} in {period}",
                          value=float(value), unit="%", display=format_value(float(value), "%"), method="yoy",
                          params={"period": period}, source_keys=[key]))
    if growth.dropna().size:
        avg = float(growth.dropna().mean())
        facts.append(Fact(key=f"yoy_avg:{ref}:{s.index[0]}-{s.index[-1]}",
                          label=f"Average YoY growth of {_short(ref)}, {s.index[0]}-{s.index[-1]}",
                          value=avg, unit="%", display=format_value(avg, "%"), method="yoy_mean",
                          params={"from": s.index[0], "to": s.index[-1]}, source_keys=[key]))
    return [ctx.add_fact(f) for f in facts]


def trend(ctx: RunContext, ref: str, start: str | None = None, end: str | None = None) -> list[Fact]:
    s, unit, key = get_series(ctx, ref)
    s = _window(s, start, end)
    x = np.arange(len(s), dtype=float)
    res = stats.linregress(x, s.values.astype(float))
    name = _short(ref)
    window = f"{s.index[0]}-{s.index[-1]}"
    facts = [
        Fact(key=f"trend_slope:{ref}:{window}", label=f"Linear trend of {name} per period, {window}",
             value=float(res.slope), unit=unit, display=format_value(float(res.slope), unit) + " per period",
             method="ols_slope", params={"window": window, "n": len(s)}, source_keys=[key]),
        Fact(key=f"trend_r2:{ref}:{window}", label=f"R-squared of linear trend for {name}, {window}",
             value=float(res.rvalue ** 2), unit="ratio", display=f"{res.rvalue ** 2:.2f}", method="ols_r2",
             params={"window": window, "p_value": float(res.pvalue)}, source_keys=[key]),
    ]
    return [ctx.add_fact(f) for f in facts]


def share(ctx: RunContext, ref: str, total_ref: str, start: str | None = None,
          end: str | None = None) -> list[Fact]:
    part, unit, key = get_series(ctx, ref)
    total, _, total_key = get_series(ctx, total_ref)
    joined = pd.concat([part, total], axis=1, join="inner").dropna()
    joined.columns = ["part", "total"]
    joined = _window(joined["part"], start, end).to_frame().join(joined["total"])
    ratio = joined["part"] / joined["total"] * 100
    facts = []
    for period in (ratio.index[0], ratio.index[-1]):
        facts.append(Fact(key=f"share:{ref}:{total_ref}:{period}",
                          label=f"Share of {_short(ref)} in {_short(total_ref)}, {period}",
                          value=float(ratio[period]), unit="%", display=format_value(float(ratio[period]), "%"),
                          method="share", params={"period": period}, source_keys=sorted({key, total_key})))
    return [ctx.add_fact(f) for f in facts]


def correlate(ctx: RunContext, ref_a: str, ref_b: str) -> list[Fact]:
    a, _, key_a = get_series(ctx, ref_a)
    b, _, key_b = get_series(ctx, ref_b)
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    n = len(joined)
    if n < 4:
        raise AnalyticsError(f"Only {n} overlapping periods; need at least 4 for a correlation")
    pearson = stats.pearsonr(joined.iloc[:, 0], joined.iloc[:, 1])
    spearman = stats.spearmanr(joined.iloc[:, 0], joined.iloc[:, 1])
    label = f"{_short(ref_a)} vs {_short(ref_b)}"
    window = f"{joined.index[0]}-{joined.index[-1]}"
    caveat = "small sample; interpret with caution" if n < 10 else ""
    facts = [
        Fact(key=f"pearson:{ref_a}:{ref_b}", label=f"Pearson correlation, {label} ({window}, n={n})",
             value=float(pearson.statistic), unit="r", display=f"{pearson.statistic:.2f}", method="pearson",
             params={"n": n, "p_value": float(pearson.pvalue), "window": window, "caveat": caveat},
             source_keys=sorted({key_a, key_b})),
        Fact(key=f"spearman:{ref_a}:{ref_b}", label=f"Spearman rank correlation, {label} ({window}, n={n})",
             value=float(spearman.statistic), unit="r", display=f"{spearman.statistic:.2f}", method="spearman",
             params={"n": n, "p_value": float(spearman.pvalue), "window": window, "caveat": caveat},
             source_keys=sorted({key_a, key_b})),
    ]
    return [ctx.add_fact(f) for f in facts]


def anomalies(ctx: RunContext, ref: str, z_threshold: float = 1.5) -> list[Fact]:
    s, _, key = get_series(ctx, ref)
    lag = 4 if "-Q" in str(s.index[0]) else 1
    growth = ((s / s.shift(lag) - 1) * 100).dropna()
    if len(growth) < 4:
        return []
    z = (growth - growth.mean()) / (growth.std(ddof=0) or 1)
    facts = []
    for period, score in z.items():
        if abs(score) >= z_threshold:
            facts.append(Fact(key=f"anomaly:{ref}:{period}",
                              label=f"Unusual growth in {_short(ref)} in {period} (z={score:.1f})",
                              value=float(growth[period]), unit="%", display=format_value(float(growth[period]), "%"),
                              method="zscore_anomaly", params={"period": period, "z": float(score)},
                              source_keys=[key]))
    return [ctx.add_fact(f) for f in facts]


def forecast(ctx: RunContext, ref: str, horizon: int = 2) -> list[Fact]:
    """Simple linear-trend projection with a 95% prediction interval. Labelled as a projection."""
    s, unit, key = get_series(ctx, ref)
    s = s.iloc[-8:]
    if len(s) < 4 or "-" in str(s.index[0]):
        raise AnalyticsError("Forecast supports annual series with at least 4 points")
    x = np.arange(len(s), dtype=float)
    res = stats.linregress(x, s.values.astype(float))
    resid = s.values - (res.intercept + res.slope * x)
    se = math.sqrt(float(np.sum(resid ** 2)) / max(len(s) - 2, 1))
    facts = []
    last_year = int(s.index[-1])
    for h in range(1, horizon + 1):
        xf = len(s) - 1 + h
        point = res.intercept + res.slope * xf
        spread = 1.96 * se * math.sqrt(1 + 1 / len(s) + (xf - x.mean()) ** 2 / np.sum((x - x.mean()) ** 2))
        facts.append(Fact(key=f"forecast:{ref}:{last_year + h}",
                          label=f"Projected {_short(ref)} in {last_year + h} (linear trend, projection)",
                          value=float(point), unit=unit, display=format_value(float(point), unit),
                          method="linear_projection",
                          params={"year": last_year + h, "lower": float(point - spread),
                                  "upper": float(point + spread), "basis": f"{s.index[0]}-{s.index[-1]}"},
                          source_keys=[key]))
    return [ctx.add_fact(f) for f in facts]
