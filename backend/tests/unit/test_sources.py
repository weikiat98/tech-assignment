"""Source plumbing: period parsing, snapshots, SingStat MCP -> REST -> snapshot fallback, breakers."""

from datetime import date

import pytest

from app.config import get_settings
from app.core.chaos import ChaosError, chaos
from app.sources import singstat_mcp
from app.sources.base import SnapshotStore, SourceBreaker, SourceError, looks_blocked, parse_period
from app.sources.singstat_mcp import (
    SingStatMCPAdapter,
    rank_rest_tables,
    rest_search_keywords,
    to_mcp_search_shape,
)


@pytest.mark.parametrize(("raw", "expected"), [
    ("2024", ("2024", date(2024, 1, 1), "Annual")),
    ("2023 3Q", ("2023-Q3", date(2023, 7, 1), "Quarterly")),
    ("2023-Q1", ("2023-Q1", date(2023, 1, 1), "Quarterly")),
])
def test_parse_period(raw, expected):
    assert parse_period(raw) == expected


def test_parse_period_rejects_text():
    assert parse_period("not a period") is None


def test_snapshot_round_trip(tmp_path):
    store = SnapshotStore(tmp_path)
    key = store.key_for("tool", {"a": 1})
    assert store.load_json("src", "name", key) is None
    store.save_json("src", "name/with:odd chars", key, {"x": 1})
    payload, recorded = store.load_json("src", "name/with:odd chars", key)
    assert payload == {"x": 1} and recorded


def test_rest_search_ranks_level_table_above_changes_table():
    records = [
        {"id": "M183901", "title": "Changes In Employment By Sector, (Compared To The Previous Period), Annual"},
        {"id": "M182841", "title": "Employment (Persons) By Sector, (As At Year-End), Annual"},
        {"id": "M999", "title": "Hotel Room Occupancy, Monthly"},
    ]
    ranked = rank_rest_tables("employment by sector", records)
    assert [r["id"] for r in ranked] == ["M182841", "M183901"]  # irrelevant table dropped
    shaped = to_mcp_search_shape(ranked)
    assert shaped["data"][0] == {"Employment (Persons) By Sector, (As At Year-End)": {"Annual, ": "M182841"}}


def test_rest_search_keywords_skip_stopwords():
    assert rest_search_keywords("employment by sector") == ["employment", "sector"]
    assert rest_search_keywords("employed tech and media manpower") == ["employed", "manpower", "media"]


def test_breaker_opens_after_threshold_and_on_block():
    b = SourceBreaker(threshold=2, open_seconds=60)
    b.record(False)
    assert not b.is_open
    b.record(False)
    assert b.is_open
    b.record(True)
    assert not b.is_open
    b.record(False, blocked=True)
    assert b.is_open


def test_looks_blocked_unwraps_exception_groups():
    assert looks_blocked(ExceptionGroup("tg", [RuntimeError("HTTP 429 Too Many Requests")]))
    assert not looks_blocked(RuntimeError("connection reset"))


@pytest.fixture
def adapter(monkeypatch, tmp_path):
    """SingStat adapter in online mode with fake transports and an empty snapshot store."""
    monkeypatch.setattr(get_settings(), "offline_mode", False)
    monkeypatch.setattr(singstat_mcp, "snapshots", SnapshotStore(tmp_path))
    for b in singstat_mcp.BREAKERS.values():
        b.reset()
    a = SingStatMCPAdapter()
    a.settings = get_settings()
    calls = {"mcp": 0, "rest": 0}

    async def mcp(tool, args):
        calls["mcp"] += 1
        chaos.check_source("singstat_mcp")
        return {"data": "from-mcp"}

    async def rest(tool, args):
        calls["rest"] += 1
        chaos.check_source("singstat_rest")
        return {"data": "from-rest"}

    monkeypatch.setattr(a, "_call_mcp", mcp)
    monkeypatch.setattr(a, "_call_rest", rest)
    yield a, calls
    for b in singstat_mcp.BREAKERS.values():
        b.reset()


async def test_mcp_is_primary(adapter):
    a, _ = adapter
    payload, prov = await a.call("get_table_metadata", {"resource_id": "M1"})
    assert payload == {"data": "from-mcp"} and prov["via"] == "mcp"


async def test_mcp_down_falls_back_to_rest(adapter):
    a, _ = adapter
    chaos.fail_sources = {"singstat_mcp"}
    payload, prov = await a.call("get_table_metadata", {"resource_id": "M1"})
    assert prov["via"] == "rest" and "ChaosError" in prov["fallback_reason"]


async def test_both_down_serves_snapshot_recorded_earlier(adapter):
    a, _ = adapter
    await a.call("get_table_metadata", {"resource_id": "M1"})  # records a snapshot
    chaos.fail_sources = {"singstat_mcp", "singstat_rest"}
    payload, prov = await a.call("get_table_metadata", {"resource_id": "M1"})
    assert payload == {"data": "from-mcp"} and prov["via"] == "snapshot" and prov["recorded_at"]


async def test_all_down_without_snapshot_raises(adapter):
    a, _ = adapter
    chaos.fail_sources = {"singstat_mcp", "singstat_rest"}
    with pytest.raises(SourceError, match="no snapshot"):
        await a.call("get_table_metadata", {"resource_id": "never-seen"})


async def test_rest_fallback_does_not_overwrite_mcp_snapshot(adapter):
    a, _ = adapter
    await a.call("get_table_metadata", {"resource_id": "M1"})
    chaos.fail_sources = {"singstat_mcp"}
    await a.call("get_table_metadata", {"resource_id": "M1"})  # served by REST
    chaos.fail_sources = {"singstat_mcp", "singstat_rest"}
    payload, _ = await a.call("get_table_metadata", {"resource_id": "M1"})
    assert payload == {"data": "from-mcp"}


async def test_simulated_outage_does_not_open_real_breaker(adapter):
    a, _ = adapter
    chaos.fail_sources = {"singstat_mcp"}
    for _ in range(3):
        await a.call("get_table_metadata", {"resource_id": "M1"})
    assert not singstat_mcp.BREAKERS["mcp"].is_open


async def test_real_failures_open_breaker_and_skip_mcp(adapter, monkeypatch):
    a, calls = adapter

    async def broken(tool, args):
        calls["mcp"] += 1
        raise ConnectionError("server error")

    monkeypatch.setattr(a, "_call_mcp", broken)
    await a.call("get_table_metadata", {"resource_id": "M1"})
    await a.call("get_table_metadata", {"resource_id": "M1"})
    tried = calls["mcp"]
    _, prov = await a.call("get_table_metadata", {"resource_id": "M1"})
    assert calls["mcp"] == tried  # circuit open: MCP not called again
    assert "circuit open" in prov["fallback_reason"] and prov["via"] == "rest"


async def test_offline_mode_serves_recorded_snapshot():
    """The repo ships snapshots for the demo queries; offline mode must serve them."""
    a = SingStatMCPAdapter()
    tables, prov = await a.search_tables("employment by sector")
    assert prov["via"] == "snapshot"
    assert any(t["resource_id"] == "M182841" for t in tables)


def test_chaos_error_is_raised_for_failed_source():
    chaos.fail_sources = {"datagov"}
    with pytest.raises(ChaosError):
        chaos.check_source("datagov")


def test_datagov_catalogue_search_ranks_by_title_match():
    from app.sources.datagov import search_catalogue
    catalogue = [
        {"dataset_id": "a", "title": "Primary Inputs By Final Demand", "description": "", "last_updated": "2026",
         "format": "CSV", "agency": "DOS"},
        {"dataset_id": "b", "title": "Number of Retrenched Term Contract Employees by Industry", "description": "",
         "last_updated": "2026-09", "format": "CSV", "agency": "MOM"},
        {"dataset_id": "c", "title": "Number of Retrenched Employees - Quarterly", "description": "",
         "last_updated": "2026-01", "format": "CSV", "agency": "MOM"},
        {"dataset_id": "d", "title": "Hawker centres", "description": "retrenched stall holders",
         "last_updated": "2026", "format": "CSV", "agency": "NEA"},
    ]
    assert [r["dataset_id"] for r in search_catalogue(catalogue, "retrenchments of employees")] == ["c", "b", "d"]
    assert search_catalogue(catalogue, "the and of") == []


async def test_datagov_search_uses_shipped_catalogue_index():
    from app.sources.datagov import datagov
    results, via = await datagov.search("unemployment rate")
    assert via == "catalogue index"
    assert "Unemployment Rate" in results[0]["title"]
