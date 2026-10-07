"""Build a local search index of the Data.gov.sg dataset catalogue.

    python -m app.scripts.build_datagov_index

The v2 API (`/v2/public/api/datasets`) ignores its `query` parameter: every search returns the same first
page of the whole catalogue in id order. This script pages through the catalogue once (politely, one
request at a time) and writes a compact index to data/datagov_catalogue.json, which the adapter searches
locally. Re-run it to pick up new datasets; the adapter falls back to the live API when the index is
missing.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx

from app.config import get_settings
from app.sources.datagov import CATALOGUE_PATH

PAUSE_S = 0.3


async def main() -> None:
    base = get_settings().datagov_api_base
    entries: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "policy-analytics/0.1"}) as client:
        page, pages = 1, 1
        while page <= pages:
            resp = await client.get(f"{base}/datasets", params={"page": page})
            if resp.status_code == 429:
                await asyncio.sleep(5)
                continue
            resp.raise_for_status()
            data = resp.json()["data"]
            pages = data["pages"]
            for d in data["datasets"]:
                if d.get("status", "active") != "active":
                    continue
                entries.append({
                    "dataset_id": d["datasetId"], "title": d.get("name", ""),
                    "agency": d.get("managedByAgencyName", ""), "format": d.get("format", ""),
                    "last_updated": d.get("lastUpdatedAt", ""),
                    "description": " ".join((d.get("description") or "").split())[:240],
                })
            if page % 50 == 0:
                print(f"page {page}/{pages}: {len(entries)} datasets")
            page += 1
            await asyncio.sleep(PAUSE_S)
    CATALOGUE_PATH.write_text(json.dumps({"built_at": datetime.now(UTC).isoformat(), "datasets": entries},
                                         ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(entries)} datasets to {CATALOGUE_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
