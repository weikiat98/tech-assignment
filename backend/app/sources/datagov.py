"""Data.gov.sg adapter: CSV download via the v1 open API, CKAN datastore JSON as fallback.

Verified 3 Oct 2026:
  search:   GET {v2}/datasets?query=...           -> data.datasets[{datasetId, name, format, managedByAgencyName}]
  download: GET {open}/datasets/{id}/poll-download -> data.url (signed S3 CSV link)
  json:     GET {ckan}/datastore_search?resource_id={id}
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from app.config import get_settings, is_configured
from app.core.chaos import chaos
from app.core.models import CANONICAL_COLUMNS, DatasetRecord
from app.sources.base import SourceError, parse_period, parse_value, snapshots, with_retries

SOURCE_ID = "datagov"
# Local index of the catalogue (app/scripts/build_datagov_index.py): the v2 search API ignores its query.
CATALOGUE_PATH = Path(__file__).resolve().parents[2] / "data" / "datagov_catalogue.json"
_STOPWORDS = {"the", "and", "for", "from", "with", "by", "of", "in", "on", "per", "data", "dataset"}
DATASET_URL = "https://data.gov.sg/datasets/{id}/view"
_PERIOD_COLS = re.compile(r"^(year|quarter|month|period|date|financial_year|time)$", re.I)


class DataGovAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": "policy-analytics/0.1"}
        if is_configured(self.settings.datagov_api_key):
            headers["x-api-key"] = self.settings.datagov_api_key
        return headers

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        chaos.check_source(SOURCE_ID)
        async with httpx.AsyncClient(timeout=20, headers=self._headers()) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    async def search(self, query: str, limit: int = 8) -> tuple[list[dict[str, str]], str]:
        catalogue = load_catalogue()
        if catalogue:
            chaos.check_source(SOURCE_ID)
            return search_catalogue(catalogue, query, limit), "catalogue index"
        key = snapshots.key_for("search", query)
        try:
            if self.settings.offline_mode:
                raise SourceError("offline mode")
            payload = await with_retries(self._get_json, f"{self.settings.datagov_api_base}/datasets",
                                         {"page": 1, "query": query})
            snapshots.save_json(SOURCE_ID, f"search_{query}", key, payload)
            via = "live"
        except Exception as exc:  # noqa: BLE001
            cached = snapshots.load_json(SOURCE_ID, f"search_{query}", key)
            if cached is None:
                raise SourceError(f"Data.gov.sg search failed and no snapshot: {exc}") from exc
            payload, via = cached[0], "snapshot"
        results = [
            {"dataset_id": d["datasetId"], "title": d.get("name", ""), "format": d.get("format", ""),
             "agency": d.get("managedByAgencyName", ""), "last_updated": d.get("lastUpdatedAt", "")}
            for d in payload.get("data", {}).get("datasets", [])
        ]
        # The API ranks loosely; keep results whose title shares a word with the query first.
        words = {w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 3}
        results.sort(key=lambda r: -len(words & set(re.findall(r"[a-z]+", r["title"].lower()))))
        return results[:limit], via

    async def _download_csv(self, dataset_id: str) -> bytes:
        chaos.check_source(SOURCE_ID)
        base = self.settings.datagov_open_base
        async with httpx.AsyncClient(timeout=30, headers=self._headers(), follow_redirects=True) as client:
            for attempt in range(6):
                poll = (await client.get(f"{base}/datasets/{dataset_id}/poll-download")).json()
                data = poll.get("data") or {}
                if data.get("status") == "DOWNLOAD_SUCCESS" and data.get("url"):
                    csv_resp = await client.get(data["url"])
                    csv_resp.raise_for_status()
                    return csv_resp.content
                if attempt == 0:
                    await client.get(f"{base}/datasets/{dataset_id}/initiate-download")
                await asyncio.sleep(1.5)
        raise SourceError(f"Data.gov.sg download for {dataset_id} did not become ready")

    async def _datastore_json(self, dataset_id: str) -> bytes:
        payload = await self._get_json(f"{self.settings.datagov_ckan_base}/datastore_search",
                                       {"resource_id": dataset_id, "limit": 10000})
        records = payload.get("result", {}).get("records", [])
        return pd.DataFrame(records).drop(columns=["_id"], errors="ignore").to_csv(index=False).encode()

    async def fetch(self, dataset_id: str, title: str | None = None) -> DatasetRecord:
        key = snapshots.key_for("csv", dataset_id)
        errors: list[str] = []
        content: bytes | None = None
        via = "csv"
        if not self.settings.offline_mode:
            for via_name, fn in (("csv", self._download_csv), ("datastore-json", self._datastore_json)):
                try:
                    content = await with_retries(fn, dataset_id, attempts=2)
                    snapshots.save_bytes(SOURCE_ID, dataset_id, key, content, "csv")
                    via = via_name
                    break
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{via_name}: {type(exc).__name__}: {str(exc)[:160]}")
        recorded_at = None
        if content is None:
            cached = snapshots.load_bytes(SOURCE_ID, dataset_id, key, "csv")
            if cached is None:
                raise SourceError(f"Data.gov.sg {dataset_id} unavailable and no snapshot: {'; '.join(errors)}")
            content, recorded_at = cached
            via = "snapshot"
        raw = pd.read_csv(io.BytesIO(content))
        frame, notes = self.normalise(raw, dataset_id)
        return DatasetRecord(
            key=f"{SOURCE_ID}:{dataset_id}",
            source_id=SOURCE_ID,
            dataset_id=dataset_id,
            title=title or dataset_id,
            url=DATASET_URL.format(id=dataset_id),
            unit=None,
            frequency=frame["frequency"].mode().iloc[0] if not frame.empty else None,
            retrieved_at=datetime.fromisoformat(recorded_at) if recorded_at else datetime.now(UTC),
            is_fallback=via != "csv",
            fallback_reason=(f"served via {via}: {'; '.join(errors) or 'offline mode'}" if via != "csv" else None),
            trust_tier=1,
            notes=notes + [f"Retrieved via Data.gov.sg ({via})"],
            frame=frame,
        )

    @staticmethod
    def normalise(raw: pd.DataFrame, dataset_id: str) -> tuple[pd.DataFrame, list[str]]:
        """Generic CSV -> canonical long format.

        Handles the two common Data.gov.sg shapes:
          wide: period column + one numeric column per series
          long: period column + category column(s) + one value column
        """
        notes: list[str] = []
        period_col = next((c for c in raw.columns if _PERIOD_COLS.match(str(c))), raw.columns[0])
        others = [c for c in raw.columns if c != period_col]
        numeric = [c for c in others if pd.to_numeric(raw[c], errors="coerce").notna().mean() > 0.6]
        categorical = [c for c in others if c not in numeric]
        records = []
        for _, row in raw.iterrows():
            parsed = parse_period(row[period_col])
            if parsed is None:
                notes.append(f"skipped unparseable period '{row[period_col]}'")
                continue
            if categorical and len(numeric) == 1:
                series = " / ".join(str(row[c]) for c in categorical)
                pairs = [(series, row[numeric[0]])]
            else:
                pairs = [(str(c), row[c]) for c in numeric]
            for series, cell in pairs:
                value, value_notes = parse_value(cell)
                notes.extend(f"{series} {parsed[0]}: {n}" for n in value_notes)
                records.append({
                    "source_id": SOURCE_ID, "dataset_id": dataset_id, "series": series, "series_code": "",
                    "period": parsed[0], "period_start": parsed[1], "frequency": parsed[2],
                    "value": value, "unit": "",
                })
        return pd.DataFrame.from_records(records, columns=CANONICAL_COLUMNS), sorted(set(notes))[:50]


datagov = DataGovAdapter()


@lru_cache(maxsize=1)
def load_catalogue() -> list[dict[str, str]]:
    if not CATALOGUE_PATH.exists():
        return []
    return json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))["datasets"]


def search_catalogue(catalogue: list[dict[str, str]], query: str, limit: int = 8) -> list[dict[str, str]]:
    """Keyword search: title matches count three times as much as description matches. Ties go to the
    more general title (fewer words beyond the query), then the most recently updated dataset. Words are
    matched on their first five letters, so 'retrenchments' finds 'Retrenched'."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2 and w not in _STOPWORDS]
    stems = {w[:5] for w in words}
    if not stems:
        return []

    def score(d: dict[str, str]) -> tuple[int, int, str]:
        title = {w[:5] for w in re.findall(r"[a-z0-9]+", d["title"].lower())}
        desc = {w[:5] for w in re.findall(r"[a-z0-9]+", d.get("description", "").lower())}
        return 3 * len(stems & title) + len(stems & desc), -len(title - stems), d.get("last_updated", "")

    ranked = sorted(((score(d), d) for d in catalogue), key=lambda x: x[0], reverse=True)
    return [{k: d[k] for k in ("dataset_id", "title", "format", "agency", "last_updated")}
            for sc, d in ranked[:limit] if sc[0] > 0]
