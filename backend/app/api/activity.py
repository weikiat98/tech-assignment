"""Run activity across every chat: totals per week, month or year, plus the runs in one period (decision 26)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import require_token
from app.db.models import Analysis
from app.db.session import get_session

router = APIRouter(prefix="/api/v1/activity", tags=["activity"], dependencies=[Depends(require_token)])

Period = Literal["week", "month", "year"]
ACTIVE = {"queued", "running", "awaiting_input"}
# How many periods the table shows; the cumulative count still includes everything before them.
WINDOW: dict[str, int] = {"week": 12, "month": 12, "year": 10}
RUNS_LIMIT = 200


def zone(name: str | None) -> ZoneInfo | timezone:
    """The viewer's time zone, so a run late on Sunday night counts in that week. Unknown names fall back to UTC."""
    try:
        return ZoneInfo(name) if name else UTC
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def period_start(day: date, period: str) -> date:
    if period == "week":
        return day - timedelta(days=day.weekday())  # weeks start on Monday
    if period == "month":
        return day.replace(day=1)
    return day.replace(month=1, day=1)


def next_start(start: date, period: str) -> date:
    if period == "week":
        return start + timedelta(days=7)
    if period == "month":
        return date(start.year + start.month // 12, start.month % 12 + 1, 1)
    return date(start.year + 1, 1, 1)


def label(start: date, period: str) -> str:
    if period == "week":
        return f"Week of {start.day} {start:%b %Y}"
    if period == "month":
        return f"{start:%B %Y}"
    return str(start.year)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _instant(day: date, tz: ZoneInfo | timezone) -> str:
    """Midnight at the start of `day` in the viewer's zone, as a UTC timestamp the runs query accepts."""
    return datetime.combine(day, datetime.min.time(), tz).astimezone(UTC).isoformat()


def _empty() -> dict[str, Any]:
    return {"runs": 0, "completed": 0, "failed": 0, "cancelled": 0, "active": 0, "verified": 0, "cost_usd": 0.0}


def _add(bucket: dict[str, Any], status: str, verified: bool | None, cost: float) -> None:
    bucket["runs"] += 1
    if status in ACTIVE:
        bucket["active"] += 1
    elif status in ("completed", "failed", "cancelled"):
        bucket[status] += 1
    if verified:
        bucket["verified"] += 1
    bucket["cost_usd"] += cost


def bucket_runs(rows: list[tuple[datetime, str, bool | None, float]], period: str,
                tz: ZoneInfo | timezone, today: date) -> dict[str, Any]:
    """Group (created_at, status, verified, cost) rows into periods, newest first, with a running total of runs.

    The table covers up to WINDOW periods ending at `today`, starting no earlier than the first run's period;
    empty periods in between show as zeros.
    """
    counts: dict[date, dict[str, Any]] = {}
    totals = _empty()
    for created_at, status, verified, cost in rows:
        start = period_start(_as_utc(created_at).astimezone(tz).date(), period)
        _add(counts.setdefault(start, _empty()), status, verified, cost)
        _add(totals, status, verified, cost)

    starts = [period_start(today, period)]
    for _ in range(WINDOW[period] - 1):
        starts.append(period_start(starts[-1] - timedelta(days=1), period))
    if counts:  # nothing to show before the first run
        starts = [s for s in starts if s >= min(counts)] or starts[:1]
    oldest = starts[-1]
    if period == "year" and counts:  # years are few, so show every year back to the first run
        first = min(counts)
        while oldest > first:
            oldest = period_start(oldest - timedelta(days=1), period)
            starts.append(oldest)

    cumulative = sum(b["runs"] for s, b in counts.items() if s < oldest)
    buckets = []
    for start in reversed(starts):
        b = counts.get(start, _empty())
        cumulative += b["runs"]
        buckets.append({"start": start.isoformat(), "label": label(start, period),
                        "from": _instant(start, tz), "to": _instant(next_start(start, period), tz),
                        **b, "cost_usd": round(b["cost_usd"], 4), "cumulative_runs": cumulative})
    totals["cost_usd"] = round(totals["cost_usd"], 4)
    return {"period": period, "tz": str(tz), "totals": totals, "buckets": buckets[::-1]}


@router.get("")
async def activity(period: Period = "week", tz: str | None = None, session: AsyncSession = Depends(get_session)):
    zinfo = zone(tz)
    verified = Analysis.result["verification"]["passed"].as_boolean()
    rows = (await session.execute(select(Analysis.created_at, Analysis.status, verified, Analysis.total_cost_usd))).all()
    today = datetime.now(UTC).astimezone(zinfo).date()
    return bucket_runs([(r[0], r[1], r[2], float(r[3] or 0)) for r in rows], period, zinfo, today)


@router.get("/runs")
async def runs_between(start: datetime, end: datetime, session: AsyncSession = Depends(get_session)):
    """The runs created in [start, end), newest first: the rows behind one period of the table."""
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be after start")
    stmt = (select(Analysis.id, Analysis.chat_id, Analysis.query, Analysis.status, Analysis.created_at,
                   Analysis.finished_at, Analysis.total_cost_usd,
                   Analysis.result["verification"]["passed"].as_boolean())
            .where(Analysis.created_at >= _as_utc(start), Analysis.created_at < _as_utc(end))
            .order_by(desc(Analysis.created_at)).limit(RUNS_LIMIT))
    out = []
    for r in (await session.execute(stmt)).all():
        created, finished = _as_utc(r[4]), r[5] and _as_utc(r[5])
        out.append({"id": r[0], "chat_id": r[1], "query": r[2], "status": r[3], "created_at": created.isoformat(),
                    "seconds": round((finished - created).total_seconds(), 1) if finished else None,
                    "cost_usd": float(r[6] or 0), "verified": r[7]})
    return out
