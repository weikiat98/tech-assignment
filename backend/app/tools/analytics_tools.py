"""Analytics agent tools. Each wraps a deterministic function and returns the Facts it created."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.analytics import charts, stats
from app.core.run_context import RunContext
from app.tools.base import Tool

AGENT = "analytics"


def _window(ctx: RunContext, start: str | None, end: str | None) -> tuple[str | None, str | None]:
    intent = ctx.intent
    return (start or (str(intent.start_year) if getattr(intent, "start_year", None) else None),
            end or (str(intent.end_year) if getattr(intent, "end_year", None) else None))


async def _facts_out(ctx: RunContext, facts) -> dict:
    for f in facts:
        await ctx.emit(AGENT, "fact", f.model_dump())
    return {"facts": [{"id": f.id, "label": f.label, "display": f.display} for f in facts]}


class NoArgs(BaseModel):
    pass


async def list_series(ctx: RunContext) -> dict:
    return {"series": stats.list_series(ctx)[:80]}


class SeriesArgs(BaseModel):
    ref: str = Field(description="Series reference '<dataset_key>::<series>' from list_series")
    start: str | None = Field(None, description="First period, e.g. '2020' (defaults to the query range)")
    end: str | None = None


def _series_tool(fn):
    async def run(ctx: RunContext, ref: str, start: str | None, end: str | None) -> dict:
        s, e = _window(ctx, start, end)
        return await _facts_out(ctx, fn(ctx, ref, s, e))
    return run


class ShareArgs(SeriesArgs):
    total_ref: str = Field(description="Series reference of the total (denominator)")


async def share(ctx: RunContext, ref: str, total_ref: str, start: str | None, end: str | None) -> dict:
    s, e = _window(ctx, start, end)
    return await _facts_out(ctx, stats.share(ctx, ref, total_ref, s, e))


class PairArgs(BaseModel):
    ref_a: str
    ref_b: str


async def correlate(ctx: RunContext, ref_a: str, ref_b: str) -> dict:
    return await _facts_out(ctx, stats.correlate(ctx, ref_a, ref_b))


class RefArgs(BaseModel):
    ref: str


async def anomalies(ctx: RunContext, ref: str) -> dict:
    return await _facts_out(ctx, stats.anomalies(ctx, ref))


class ForecastArgs(BaseModel):
    ref: str
    horizon: int = Field(2, ge=1, le=3)


async def forecast(ctx: RunContext, ref: str, horizon: int) -> dict:
    return await _facts_out(ctx, stats.forecast(ctx, ref, horizon))


class ChartArgs(BaseModel):
    kind: str = Field(description="line | indexed | yoy_bar | scatter | forecast")
    refs: list[str] = Field(description="Series references (scatter: exactly two)")
    title: str


async def make_chart(ctx: RunContext, kind: str, refs: list[str], title: str) -> dict:
    s, e = _window(ctx, None, None)
    if kind == "line":
        chart = charts.line(ctx, refs, title, s, e)
    elif kind == "indexed":
        chart = charts.indexed(ctx, refs, title, s, e)
    elif kind == "yoy_bar":
        chart = charts.yoy_bar(ctx, refs[0], title)
    elif kind == "scatter":
        chart = charts.scatter(ctx, refs[0], refs[1], title)
    elif kind == "forecast":
        chart = charts.forecast_fan(ctx, refs[0], title)
    else:
        return {"error": f"Unknown chart kind '{kind}'"}
    await ctx.emit(AGENT, "chart", chart.model_dump())
    return {"chart_id": chart.id, "title": chart.title}


ANALYTICS_TOOLS: list[Tool] = [
    Tool("list_series", "List every available series reference with unit and period range.", NoArgs, list_series),
    Tool("describe", "Start/end levels and peak of a series.", SeriesArgs, _series_tool(stats.describe)),
    Tool("change", "Absolute and percent change over the window.", SeriesArgs, _series_tool(stats.change)),
    Tool("cagr", "Compound annual growth rate over the window.", SeriesArgs, _series_tool(stats.cagr)),
    Tool("yoy", "Year-on-year growth for each period plus the average.", SeriesArgs, _series_tool(stats.yoy)),
    Tool("trend", "OLS linear trend slope and R-squared.", SeriesArgs, _series_tool(stats.trend)),
    Tool("share", "Share of a series in a total series at the start and end of the window.", ShareArgs, share),
    Tool("correlate", "Pearson and Spearman correlation between two series over overlapping periods.",
         PairArgs, correlate),
    Tool("anomalies", "Flag periods with unusual growth (z-score).", RefArgs, anomalies),
    Tool("forecast", "Linear-trend projection with 95% interval (clearly labelled as a projection).",
         ForecastArgs, forecast),
    Tool("make_chart", "Create a Plotly chart: line, indexed, yoy_bar, scatter or forecast.", ChartArgs, make_chart),
]
