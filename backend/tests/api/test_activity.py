"""Run activity: weekly/monthly/yearly totals with a running count, and the runs behind one period."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.api.activity import bucket_runs, label, next_start, period_start, zone
from app.main import app, lifespan

SGT = ZoneInfo("Asia/Singapore")


def at(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=UTC)


def test_period_boundaries():
    wed = date(2026, 10, 14)
    assert period_start(wed, "week") == date(2026, 10, 12)  # Monday
    assert period_start(wed, "month") == date(2026, 10, 1)
    assert period_start(wed, "year") == date(2026, 1, 1)
    assert next_start(date(2026, 12, 1), "month") == date(2027, 1, 1)
    assert next_start(date(2026, 10, 12), "week") == date(2026, 10, 19)
    assert label(date(2026, 10, 12), "week") == "Week of 12 Oct 2026"
    assert label(date(2026, 10, 1), "month") == "October 2026"


def test_unknown_zone_falls_back_to_utc():
    assert zone("Not/AZone") == UTC
    assert zone(None) == UTC


def test_weekly_buckets_count_statuses_and_keep_a_running_total():
    rows = [
        (at(2026, 10, 13), "completed", True, 0.01),
        (at(2026, 10, 14), "failed", None, 0.002),
        (at(2026, 10, 6), "completed", False, 0.01),
        (at(2026, 10, 15), "running", None, 0.0),
        (at(2025, 1, 1), "completed", True, 0.0),  # long before the 12-week window
    ]
    out = bucket_runs(rows, "week", UTC, date(2026, 10, 15))
    assert len(out["buckets"]) == 12
    this_week, last_week = out["buckets"][0], out["buckets"][1]
    assert this_week["start"] == "2026-10-12"
    assert (this_week["runs"], this_week["completed"], this_week["failed"], this_week["active"]) == (3, 1, 1, 1)
    assert this_week["verified"] == 1 and this_week["cost_usd"] == 0.012
    assert last_week["runs"] == 1 and last_week["verified"] == 0
    # The running total starts from the run before the window and ends at every run.
    assert out["buckets"][-1]["cumulative_runs"] == 1
    assert this_week["cumulative_runs"] == 5
    assert out["totals"]["runs"] == 5 and out["totals"]["verified"] == 2


def test_periods_before_the_first_run_are_left_out():
    out = bucket_runs([(at(2026, 9, 30), "completed", True, 0.0)], "week", UTC, date(2026, 10, 15))
    assert [b["start"] for b in out["buckets"]] == ["2026-10-12", "2026-10-05", "2026-09-28"]
    assert len(bucket_runs([], "month", UTC, date(2026, 10, 15))["buckets"]) == 12


def test_runs_are_bucketed_in_the_viewers_zone():
    # 17:00 UTC on Sunday 11 Oct is 01:00 on Monday 12 Oct in Singapore.
    rows = [(datetime(2026, 10, 11, 17, tzinfo=UTC), "completed", True, 0.0)]
    assert bucket_runs(rows, "week", UTC, date(2026, 10, 15))["buckets"][1]["runs"] == 1
    sg = bucket_runs(rows, "week", SGT, date(2026, 10, 15))
    assert sg["buckets"][0]["runs"] == 1
    assert sg["buckets"][0]["from"] == "2026-10-11T16:00:00+00:00"


def test_years_reach_back_to_the_first_run():
    rows = [(at(2012, 5, 1), "completed", True, 0.0), (at(2026, 2, 1), "completed", True, 0.0)]
    out = bucket_runs(rows, "year", UTC, date(2026, 10, 15))
    assert out["buckets"][0]["label"] == "2026" and out["buckets"][-1]["label"] == "2012"
    assert out["buckets"][0]["cumulative_runs"] == 2


@pytest.fixture(scope="module")
async def client():
    async with lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_activity_routes(client):
    await client.post("/api/v1/chats", json={"query": "Analyse employment trends in the technology sector from 2020-2024"})
    body = (await client.get("/api/v1/activity", params={"period": "month", "tz": "Asia/Singapore"})).json()
    assert body["period"] == "month" and body["tz"] == "Asia/Singapore"
    current = body["buckets"][0]
    assert current["runs"] >= 1 and body["totals"]["runs"] >= current["runs"]

    runs = (await client.get("/api/v1/activity/runs", params={"start": current["from"], "end": current["to"]})).json()
    assert len(runs) == current["runs"]
    assert {"id", "chat_id", "query", "status", "created_at", "seconds", "cost_usd", "verified"} <= runs[0].keys()

    assert (await client.get("/api/v1/activity", params={"period": "day"})).status_code == 422
    bad = await client.get("/api/v1/activity/runs", params={"start": current["to"], "end": current["from"]})
    assert bad.status_code == 422
