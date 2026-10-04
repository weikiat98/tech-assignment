"""DOS SingStat adapter: official SingStat MCP server first, REST API second, snapshots last.

MCP server (verified 3 Oct 2026): https://chatwithsandra.singstat.gov.sg/mcp
  - get_relevant_table_names(query_text)
  - get_table_metadata(resource_id)
  - get_table_data(resource_id, seriesNoORrowNo?, timeFilter?, offset?)   (max 3,000 rows)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pandas as pd
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings
from app.core.chaos import chaos
from app.core.models import CANONICAL_COLUMNS, DatasetRecord
from app.sources.base import SourceError, parse_period, parse_value, snapshots, with_retries, year_filter

SOURCE_ID = "singstat"
TABLE_URL = "https://tablebuilder.singstat.gov.sg/table/TS/{rid}"


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
                resp = await client.get(f"{base}/resourceid", params={
                    "keyword": arguments["query_text"], "searchOption": "all"})
                resp.raise_for_status()
                records = (resp.json().get("Data") or {}).get("records", [])
                return {"data": [{r.get("title", r.get("id")): {r.get("frequency", "") + ", ": r.get("id")}}
                                 for r in records]}
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
                try:
                    payload = await with_retries(fn, tool, arguments, attempts=2 if via == "rest" else 3)
                    snapshots.save_json(SOURCE_ID, name, key, payload)
                    reason = "; ".join(errors) or None
                    return payload, FetchProvenance(via=via, fallback_reason=reason, recorded_at=None)
                except Exception as exc:  # noqa: BLE001 - every failure moves to the next fallback
                    errors.append(f"{via}: {type(exc).__name__}: {str(exc)[:160]}")
        cached = snapshots.load_json(SOURCE_ID, name, key)
        if cached is None:
            raise SourceError("SingStat unavailable and no snapshot recorded. " + "; ".join(errors))
        payload, recorded_at = cached
        reason = "; ".join(errors) or "offline mode"
        return payload, FetchProvenance(via="snapshot", fallback_reason=reason, recorded_at=recorded_at)

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
