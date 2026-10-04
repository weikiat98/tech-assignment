"""MOM statistics Excel adapter.

MOM publishes labour-market tables as .xlsx with multi-row headers, footnotes and
markers such as '-' or 'p' (provisional). The parser finds the header row by looking
for a row with several year-like cells, then unpivots wide -> long.

Source of the workbook, in order: an explicit URL (e.g. found by the agent's web
search), MOM_EXCEL_URL, then the bundled sample workbook in data/mom/.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from app.config import BACKEND_ROOT, get_settings, is_configured
from app.core.chaos import chaos
from app.core.models import CANONICAL_COLUMNS, DatasetRecord
from app.sources.base import SourceError, parse_period, parse_value, snapshots, with_retries

SOURCE_ID = "mom"
SAMPLE_WORKBOOK = BACKEND_ROOT / "data" / "mom" / "mom_employment_by_industry_sample.xlsx"


class MOMExcelAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def _download(self, url: str) -> bytes:
        chaos.check_source(SOURCE_ID)
        async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                     headers={"User-Agent": "policy-analytics/0.1"}) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def fetch(self, url: str | None = None, sheet: str | int = 0) -> DatasetRecord:
        target = url or (self.settings.mom_excel_url if is_configured(self.settings.mom_excel_url) else None)
        notes: list[str] = []
        content: bytes | None = None
        is_fallback, reason, origin = False, None, target
        if target and not self.settings.offline_mode:
            key = snapshots.key_for("xlsx", target)
            try:
                content = await with_retries(self._download, target, attempts=2)
                snapshots.save_bytes(SOURCE_ID, Path(target).stem or "workbook", key, content, "xlsx")
            except Exception as exc:  # noqa: BLE001
                cached = snapshots.load_bytes(SOURCE_ID, Path(target).stem or "workbook", key, "xlsx")
                if cached:
                    content, is_fallback, reason = cached[0], True, f"download failed ({exc}); served snapshot"
                else:
                    reason = f"download failed ({exc}); using bundled sample workbook"
        if content is None:
            if not SAMPLE_WORKBOOK.exists():
                raise SourceError("No MOM workbook available (no URL, no snapshot, no bundled sample).")
            content = SAMPLE_WORKBOOK.read_bytes()
            origin = str(SAMPLE_WORKBOOK.name)
            is_fallback = bool(target)
            notes.append("Bundled sample workbook: MOM-sourced figures (via SingStat Table Builder) laid out "
                         "in MOM's Excel publication format to exercise the Excel parser.")
        frame, title, parse_notes = self.parse(content, sheet)
        return DatasetRecord(
            key=f"{SOURCE_ID}:{Path(origin or 'workbook').stem}", source_id=SOURCE_ID,
            dataset_id=Path(origin or "workbook").stem, title=title,
            url=target if target and target.startswith("http") else "https://stats.mom.gov.sg",
            unit=frame["unit"].mode().iloc[0] if not frame.empty else None, frequency="Annual",
            retrieved_at=datetime.now(UTC), is_fallback=is_fallback, fallback_reason=reason, trust_tier=1,
            notes=notes + parse_notes, data_source_agency="Ministry of Manpower", frame=frame,
        )

    @staticmethod
    def parse(content: bytes, sheet: str | int = 0) -> tuple[pd.DataFrame, str, list[str]]:
        grid = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=None, dtype=object)
        notes: list[str] = []
        title = str(grid.iloc[0, 0]) if not grid.empty else "MOM table"
        header_idx = None
        for idx, row in grid.iterrows():
            if sum(parse_period(v) is not None for v in row.dropna().tolist()) >= 3:
                header_idx = idx
                break
        if header_idx is None:
            raise SourceError("Could not find a header row with periods in the MOM workbook.")
        header = grid.iloc[header_idx].tolist()
        unit = ""
        for r in range(0, int(header_idx)):
            cell = str(grid.iloc[r, 0])
            if cell.lower().startswith("unit"):
                unit = cell.split(":", 1)[-1].strip()
        records = []
        for _, row in grid.iloc[int(header_idx) + 1:].iterrows():
            label = row.iloc[0]
            if pd.isna(label) or str(label).strip() == "":
                continue
            label = str(label).strip()
            if label.lower().startswith(("note", "source", "footnote", "*")):
                notes.append(label)
                continue
            for col_idx, head in enumerate(header):
                parsed = parse_period(head) if head is not None and not pd.isna(head) else None
                if parsed is None:
                    continue
                value, value_notes = parse_value(row.iloc[col_idx])
                notes.extend(f"{label} {parsed[0]}: {n}" for n in value_notes)
                records.append({
                    "source_id": SOURCE_ID, "dataset_id": "mom_excel", "series": label.lstrip(" -"),
                    "series_code": "", "period": parsed[0], "period_start": parsed[1],
                    "frequency": parsed[2], "value": value, "unit": unit,
                })
        frame = pd.DataFrame.from_records(records, columns=CANONICAL_COLUMNS)
        return frame, title, sorted(set(notes))[:50]


mom = MOMExcelAdapter()
