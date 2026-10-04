"""Plotly figure specs as plain dicts (rendered by react-plotly.js and by the PDF export)."""

from __future__ import annotations

import pandas as pd

from app.analytics.stats import get_series, split_ref
from app.core.models import Chart
from app.core.run_context import RunContext

PALETTE = ["#2563eb", "#d97706", "#059669", "#db2777", "#7c3aed", "#0891b2", "#65a30d", "#dc2626"]


def _layout(title: str, y_title: str = "", x_title: str = "") -> dict:
    return {
        "title": {"text": title, "font": {"size": 15}},
        "xaxis": {"title": {"text": x_title}, "type": "category"},
        "yaxis": {"title": {"text": y_title}, "zeroline": False},
        "legend": {"orientation": "h", "y": -0.2},
        "margin": {"l": 60, "r": 20, "t": 50, "b": 60},
        "hovermode": "x unified",
    }


def line(ctx: RunContext, refs: list[str], title: str, start: str | None = None, end: str | None = None) -> Chart:
    traces, unit, keys = [], "", set()
    for i, ref in enumerate(refs):
        s, unit, key = get_series(ctx, ref)
        s = s[(s.index >= (start or "")) & (s.index <= (end or "9999") + "~")]
        keys.add(key)
        traces.append({"type": "scatter", "mode": "lines+markers", "name": split_ref(ref)[1],
                       "x": list(s.index), "y": [round(v, 3) for v in s.values],
                       "line": {"color": PALETTE[i % len(PALETTE)], "width": 2}})
    return ctx.add_chart(Chart(title=title, kind="line", spec={"data": traces, "layout": _layout(title, unit)},
                               source_keys=sorted(keys)))


def indexed(ctx: RunContext, refs: list[str], title: str, start: str | None = None, end: str | None = None) -> Chart:
    traces, keys = [], set()
    for i, ref in enumerate(refs):
        s, _, key = get_series(ctx, ref)
        s = s[(s.index >= (start or "")) & (s.index <= (end or "9999") + "~")]
        if s.empty or s.iloc[0] == 0:
            continue
        keys.add(key)
        idx = s / s.iloc[0] * 100
        traces.append({"type": "scatter", "mode": "lines+markers", "name": split_ref(ref)[1],
                       "x": list(idx.index), "y": [round(v, 2) for v in idx.values],
                       "line": {"color": PALETTE[i % len(PALETTE)], "width": 2}})
    base = traces[0]["x"][0] if traces else ""
    return ctx.add_chart(Chart(title=title, kind="indexed",
                               spec={"data": traces, "layout": _layout(title, f"Index ({base} = 100)")},
                               source_keys=sorted(keys)))


def yoy_bar(ctx: RunContext, ref: str, title: str) -> Chart:
    s, _, key = get_series(ctx, ref)
    lag = 4 if "-Q" in str(s.index[0]) else 1
    growth = ((s / s.shift(lag) - 1) * 100).dropna()
    colors = [PALETTE[0] if v >= 0 else PALETTE[7] for v in growth.values]
    trace = {"type": "bar", "name": "YoY %", "x": list(growth.index), "y": [round(v, 2) for v in growth.values],
             "marker": {"color": colors}}
    return ctx.add_chart(Chart(title=title, kind="bar", spec={"data": [trace], "layout": _layout(title, "% YoY")},
                               source_keys=[key]))


def scatter(ctx: RunContext, ref_a: str, ref_b: str, title: str) -> Chart:
    a, unit_a, key_a = get_series(ctx, ref_a)
    b, unit_b, key_b = get_series(ctx, ref_b)
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    trace = {"type": "scatter", "mode": "markers+text", "x": [round(v, 3) for v in joined.iloc[:, 0]],
             "y": [round(v, 3) for v in joined.iloc[:, 1]], "text": list(joined.index), "textposition": "top center",
             "marker": {"size": 10, "color": PALETTE[0]}, "name": "periods"}
    layout = _layout(title, f"{split_ref(ref_b)[1]} ({unit_b})", f"{split_ref(ref_a)[1]} ({unit_a})")
    layout["xaxis"]["type"] = "linear"
    layout["hovermode"] = "closest"
    return ctx.add_chart(Chart(title=title, kind="scatter", spec={"data": [trace], "layout": layout},
                               source_keys=sorted({key_a, key_b})))


def forecast_fan(ctx: RunContext, ref: str, title: str) -> Chart:
    s, unit, key = get_series(ctx, ref)
    projections = sorted((f for f in ctx.facts.values() if f.method == "linear_projection"
                          and f.key.startswith(f"forecast:{ref}:")), key=lambda f: f.params["year"])
    hist = {"type": "scatter", "mode": "lines+markers", "name": "Actual", "x": list(s.index),
            "y": [round(v, 3) for v in s.values], "line": {"color": PALETTE[0]}}
    xs = [s.index[-1]] + [str(f.params["year"]) for f in projections]
    proj = {"type": "scatter", "mode": "lines+markers", "name": "Projection", "x": xs,
            "y": [round(float(s.iloc[-1]), 3)] + [round(f.value, 3) for f in projections],
            "line": {"color": PALETTE[1], "dash": "dash"}}
    band = {"type": "scatter", "name": "95% interval", "x": xs + xs[::-1],
            "y": [float(s.iloc[-1])] + [f.params["upper"] for f in projections]
                 + [f.params["lower"] for f in projections][::-1] + [float(s.iloc[-1])],
            "fill": "toself", "fillcolor": "rgba(217,119,6,0.15)", "line": {"width": 0}, "hoverinfo": "skip"}
    return ctx.add_chart(Chart(title=title, kind="forecast", spec={"data": [band, hist, proj],
                                                                   "layout": _layout(title, unit)},
                               fact_ids=[f.id for f in projections], source_keys=[key]))
