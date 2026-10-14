"""DOS SingStat adapter: official SingStat MCP server first, REST API second, snapshots last.

MCP server (verified 3 Oct 2026): https://chatwithsandra.singstat.gov.sg/mcp
  - get_relevant_table_names(query_text)
  - get_table_metadata(resource_id)
  - get_table_data(resource_id, seriesNoORrowNo?, timeFilter?, offset?)   (max 3,000 rows)
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings
from app.core.chaos import ChaosError, chaos
from app.core.models import CANONICAL_COLUMNS, DatasetRecord
from app.sources.base import (
    SourceBreaker,
    SourceError,
    looks_blocked,
    parse_period,
    parse_value,
    snapshots,
    with_retries,
    year_filter,
)

SOURCE_ID = "singstat"
TABLE_URL = "https://tablebuilder.singstat.gov.sg/table/TS/{rid}"
# Shared across runs: a blocked or down transport is skipped for a while instead of retried on every call.
BREAKERS = {"mcp": SourceBreaker(), "rest": SourceBreaker()}
_STOPWORDS = {"by", "the", "and", "of", "in", "for", "to", "a", "an", "on", "at", "per", "from", "with"}
_FREQ_SUFFIX = re.compile(r",\s*(Annual|Half-Yearly|Quarterly|Monthly|Weekly|Daily)$", re.I)


def rank_rest_tables(query: str, records: list[dict[str, Any]], limit: int = 15) -> list[dict[str, Any]]:
    """Rank Table Builder search records by how many query keywords their title contains.

    The REST search is a plain substring match on the whole keyword string, so the MCP-style
    query "employment by sector" misses "Employment (Persons) By Sector". The fallback searches
    each keyword separately and ranks the union here. Derived tables ("changes in", "compared to")
    rank below level tables unless the query asks for changes.
    """
    tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in _STOPWORDS and len(t) > 1]
    wants_change = any(t.startswith("change") for t in tokens)

    def score(r: dict[str, Any]) -> tuple[float, int]:
        title = r.get("title", "").lower()
        hits = sum(1 for t in tokens if t in title)
        if not wants_change and ("change" in title or "compared to" in title):
            hits -= 0.5
        return hits, -len(title)

    unique = {r["id"]: r for r in records if r.get("id")}
    ranked = sorted(unique.values(), key=score, reverse=True)
    return [r for r in ranked if score(r)[0] > 0][:limit]


def rest_search_keywords(query: str, max_keywords: int = 3) -> list[str]:
    """The most distinctive keywords of a query (longest first), each searched separately."""
    tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in _STOPWORDS and len(t) > 2]
    return sorted(dict.fromkeys(tokens), key=len, reverse=True)[:max_keywords] or [query]


def to_mcp_search_shape(records: list[dict[str, Any]]) -> dict[str, Any]:
    """REST records -> the MCP's {'data': [{title: {'Annual, ': id}}]} shape."""
    groups: dict[str, dict[str, str]] = {}
    for r in records:
        title = r.get("title") or r["id"]
        m = _FREQ_SUFFIX.search(title)
        base, freq = (title[:m.start()], m.group(1).title()) if m else (title, "")
        groups.setdefault(base, {})[f"{freq}, " if freq else ""] = r["id"]
    return {"data": [{title: variants} for title, variants in groups.items()]}


def _root_message(exc: BaseException) -> str:
    """Unwrap ExceptionGroups (the MCP client raises them) to the first real error message."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}" if not str(exc).startswith(type(exc).__name__) else str(exc)


class FetchProvenance(dict):
    """{'via': 'mcp'|'rest'|'snapshot', 'fallback_reason': str|None, 'recorded_at': str|None}"""


class SingStatMCPAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    # --- transport ------------------------------------------------------------------

    async def _call_mcp(self, tool: str, arguments: dict[str, Any]) -> Any:
        chaos.check_source("singstat_mcp")
        async with streamable_http_client(self.settings.singstat_mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments)
        if result.is_error:
            text = result.content[0].text if result.content else "unknown error"
            raise SourceError(f"SingStat MCP tool {tool} returned an error: {text}")
        if result.structured_content:
            return result.structured_content
        return json.loads(result.content[0].text)

    async def _call_rest(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Direct Table Builder REST fallback (same resource ids).

        Endpoints verified reachable 3 Oct 2026. The REST time filter uses a different format
        from the MCP's, so the whole table is fetched and years are filtered locally.
        """
        chaos.check_source("singstat_rest")
        base = self.settings.singstat_rest_base
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "policy-analytics/0.1"}) as client:
            if tool == "get_relevant_table_names":
                query = arguments["query_text"]
                records: list[dict[str, Any]] = []
                for keyword in rest_search_keywords(query):
                    resp = await client.get(f"{base}/resourceid", params={"keyword": keyword, "searchOption": "all"})
                    resp.raise_for_status()
                    records += (resp.json().get("Data") or {}).get("records") or []
                return to_mcp_search_shape(rank_rest_tables(query, records))
            if tool == "get_table_metadata":
                resp = await client.get(f"{base}/metadata/{arguments['resource_id']}")
                resp.raise_for_status()
                return {"data": {"records": resp.json().get("Data", {}).get("records", resp.json().get("Data"))}}
            params: dict[str, Any] = {"limit": 3000}
            if arguments.get("seriesNoORrowNo"):
                params["seriesNoORrowNo"] = arguments["seriesNoORrowNo"]
            if arguments.get("offset"):
                params["offset"] = arguments["offset"]
            resp = await client.get(f"{base}/tabledata/{arguments['resource_id']}", params=params)
            resp.raise_for_status()
            return {"data": resp.json().get("Data")}

    async def call(self, tool: str, arguments: dict[str, Any]) -> tuple[Any, FetchProvenance]:
        """MCP -> REST -> snapshot, recording every live success as a snapshot."""
        key = snapshots.key_for(tool, arguments)
        name = f"{tool}_{arguments.get('resource_id') or arguments.get('query_text', '')}"
        errors: list[str] = []
        if not self.settings.offline_mode:
            for via, fn in (("mcp", self._call_mcp), ("rest", self._call_rest)):
                breaker = BREAKERS[via]
                if breaker.is_open:
                    errors.append(f"{via}: skipped (circuit open after repeated failures)")
                    continue
                try:
                    payload = await with_retries(fn, tool, arguments, attempts=2)
                    breaker.record(True)
                    # A fallback response only fills a gap: it must not replace the primary (MCP) recording,
                    # whose search ranking the offline demo relies on.
                    if via == "mcp" or snapshots.load_json(SOURCE_ID, name, key) is None:
                        snapshots.save_json(SOURCE_ID, name, key, payload)
                    reason = "; ".join(errors) or None
                    return payload, FetchProvenance(via=via, fallback_reason=reason, recorded_at=None)
                except Exception as exc:  # noqa: BLE001 - every failure moves to the next fallback
                    if not isinstance(exc, ChaosError):  # a demo outage must not leave the breaker open afterwards
                        breaker.record(False, blocked=looks_blocked(exc))
                    errors.append(f"{via}: {_root_message(exc)[:160]}")
        cached = snapshots.load_json(SOURCE_ID, name, key)
        if cached is None and tool == "get_table_data":
            cached = self._nearest_table_snapshot(name, arguments)
        if cached is None:
            raise SourceError("SingStat unavailable and no snapshot recorded. " + "; ".join(errors))
        payload, recorded_at = cached
        reason = "; ".join(errors) or "offline mode"
        return payload, FetchProvenance(via="snapshot", fallback_reason=reason, recorded_at=recorded_at)

    @staticmethod
    def _nearest_table_snapshot(name: str, arguments: dict[str, Any]) -> tuple[Any, str] | None:
        """Offline: serve a request for some series of a table from a recording of the same table that holds
        them all (a follow-up asks for other sectors than the question that was recorded). Rows are filtered
        to the requested series, so the result is exactly what the live call would have returned."""
        wanted = [s for s in str(arguments.get("seriesNoORrowNo") or "").split(",") if s]
        if not wanted:
            return None
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:60]
        for path in sorted((snapshots.root / SOURCE_ID).glob(f"{safe}__*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            payload = record["payload"]
            data = payload.get("data", payload)
            rows = {str(r.get("seriesNo")): r for r in data.get("row", [])}
            if all(s in rows for s in wanted):
                trimmed = {**payload, "data": {**data, "row": [rows[s] for s in wanted]}}
                return trimmed, record.get("recorded_at", "unknown")
        return None

    # --- high-level operations --------------------------------------------------------

    async def search_tables(self, query: str) -> tuple[list[dict[str, str]], FetchProvenance]:
        payload, prov = await self.call("get_relevant_table_names", {"query_text": query})
        tables: list[dict[str, str]] = []
        for group in payload.get("data", []):
            for title, variants in group.items():
                for freq, rid in variants.items():
                    tables.append({"title": title, "frequency": freq.strip(" ,") or "Unknown",
                                   "resource_id": rid})
        return tables, prov

    async def get_metadata(self, resource_id: str) -> tuple[dict[str, Any], FetchProvenance]:
        payload, prov = await self.call("get_table_metadata", {"resource_id": resource_id})
        data = payload.get("data", payload)
        return data.get("records", data), prov

    async def fetch(self, resource_id: str, series: list[str] | None = None,
                    start_year: int | None = None, end_year: int | None = None) -> DatasetRecord:
        args: dict[str, Any] = {"resource_id": resource_id}
        if series:
            args["seriesNoORrowNo"] = ",".join(series)
        if start_year or end_year:
            args["timeFilter"] = [f"{start_year or 1900}-01", f"{end_year or 2100}-12"]
        payload, prov = await self.call("get_table_data", args)
        data = payload.get("data", payload)
        frame, notes = self.normalise(data)
        frame = year_filter(frame, start_year, end_year).reset_index(drop=True)
        record = DatasetRecord(
            key=f"{SOURCE_ID}:{resource_id}",
            source_id=SOURCE_ID,
            dataset_id=resource_id,
            title=data.get("title", resource_id),
            url=TABLE_URL.format(rid=resource_id),
            unit=_dominant_unit(frame),
            frequency=data.get("frequency"),
            retrieved_at=datetime.now(UTC) if prov["via"] != "snapshot" else _parse_ts(prov["recorded_at"]),
            is_fallback=prov["via"] != "mcp",
            fallback_reason=(f"served via {prov['via']}: {prov['fallback_reason']}"
                             if prov["via"] != "mcp" else None),
            trust_tier=1,
            footnote=data.get("footnote"),
            data_source_agency=data.get("datasource") or data.get("dataSource"),
            notes=notes + [f"Retrieved via SingStat {prov['via'].upper()}"],
            frame=frame,
        )
        return record

    # --- normalisation ------------------------------------------------------------------

    @staticmethod
    def normalise(data: dict[str, Any]) -> tuple[pd.DataFrame, list[str]]:
        rows = data.get("row", [])
        by_code = {r.get("seriesNo"): r.get("rowText") for r in rows}
        text_counts: dict[str, int] = {}
        for r in rows:
            text_counts[r.get("rowText", "")] = text_counts.get(r.get("rowText", ""), 0) + 1
        records, notes = [], []
        for r in rows:
            code = str(r.get("seriesNo", ""))
            label = r.get("rowText", code)
            if text_counts.get(label, 0) > 1 and "." in code:
                parent = by_code.get(code.rsplit(".", 1)[0])
                label = f"{parent} > {label}" if parent else f"{label} ({code})"
            for col in r.get("columns", []):
                parsed = parse_period(col.get("key"))
                if parsed is None:
                    notes.append(f"skipped unparseable period '{col.get('key')}'")
                    continue
                value, value_notes = parse_value(col.get("value"))
                notes.extend(f"{label} {parsed[0]}: {n}" for n in value_notes)
                records.append({
                    "source_id": SOURCE_ID, "dataset_id": data.get("id", ""), "series": label,
                    "series_code": code, "period": parsed[0], "period_start": parsed[1],
                    "frequency": parsed[2], "value": value, "unit": r.get("uoM") or "",
                })
        frame = pd.DataFrame.from_records(records, columns=CANONICAL_COLUMNS)
        return frame, sorted(set(notes))[:50]


def _dominant_unit(frame: pd.DataFrame) -> str | None:
    if frame.empty:
        return None
    return str(frame["unit"].mode().iloc[0])


def _parse_ts(value: str | None) -> datetime:
    try:
        return datetime.fromisoformat(value) if value else datetime.now(UTC)
    except ValueError:
        return datetime.now(UTC)


singstat = SingStatMCPAdapter()
