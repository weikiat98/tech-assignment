"""Build the bundled MOM-style sample workbook and record source snapshots for offline demos.

    python -m app.scripts.build_samples

1. Fetches MOM-sourced "Employment (Persons) By Sector" (SingStat M182841) via the MCP and
   writes it in MOM's Excel publication layout (title rows, unit row, header row, footnotes,
   '-' markers) to data/mom/ - clearly labelled as a sample built from official figures.
2. Records MCP / Data.gov.sg responses for the demo queries into data/snapshots/.
"""

from __future__ import annotations

import asyncio

from openpyxl import Workbook

from app.agents.vocab import DATAGOV_SEARCH, SINGSTAT_SEARCH
from app.sources.datagov import datagov
from app.sources.mom import SAMPLE_WORKBOOK
from app.sources.singstat_mcp import singstat

DEMO_TABLES = ["M182841", "M651561", "M183911", "M184071", "M016011", "M183901"]


async def build_mom_workbook() -> None:
    record = await singstat.fetch("M182841", None, 2015, None)
    frame = record.frame
    periods = sorted(frame["period"].unique())
    wb = Workbook()
    ws = wb.active
    ws.title = "T1"
    ws.append(["EMPLOYMENT BY INDUSTRY (AS AT YEAR-END)"])
    ws.append(["Sample workbook in MOM publication layout, built from MOM-sourced figures retrieved via "
               "SingStat Table Builder (M182841). Replace with a downloaded MOM workbook via MOM_EXCEL_URL."])
    ws.append(["Unit: Thousand"])
    ws.append([])
    ws.append(["Industry", *periods])
    for series in frame["series"].unique():
        rows = frame[frame["series"] == series].set_index("period")["value"]
        ws.append([series, *[("-" if p not in rows or rows[p] != rows[p] else float(rows[p])) for p in periods]])
    ws.append([])
    ws.append(["Note: Data are primarily from administrative records; may not add up due to rounding."])
    ws.append(["Source: Ministry of Manpower (via SingStat Table Builder)"])
    SAMPLE_WORKBOOK.parent.mkdir(parents=True, exist_ok=True)
    wb.save(SAMPLE_WORKBOOK)
    print("wrote", SAMPLE_WORKBOOK)


async def record_snapshots() -> None:
    for query, _ in SINGSTAT_SEARCH.values():
        await singstat.search_tables(query)
    await singstat.search_tables("employed tech and media manpower")
    for rid in DEMO_TABLES:
        await singstat.get_metadata(rid)
        print("metadata", rid)
    for query in set(DATAGOV_SEARCH.values()):
        results, _ = await datagov.search(query)
        if results:
            await datagov.fetch(results[0]["dataset_id"], results[0]["title"])
            print("datagov", results[0]["dataset_id"], results[0]["title"])


if __name__ == "__main__":
    asyncio.run(build_mom_workbook())
    asyncio.run(record_snapshots())
