"""Small builders for hand-made datasets, so expected values can be computed by hand."""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.models import DatasetRecord
from app.core.run_context import RunContext


def _period_start(period: str) -> date:
    if "-Q" in period:
        year, q = period.split("-Q")
        return date(int(year), 3 * (int(q) - 1) + 1, 1)
    if len(period) == 7:
        return date(int(period[:4]), int(period[5:]), 1)
    return date(int(period), 1, 1)


def frame(series: dict[str, dict[str, float | None]], source_id: str = "singstat", dataset_id: str = "T1",
          unit: str = "Thousand", frequency: str = "Annual", codes: dict[str, str] | None = None) -> pd.DataFrame:
    rows = []
    for i, (name, values) in enumerate(series.items(), start=1):
        for period, value in values.items():
            rows.append({"source_id": source_id, "dataset_id": dataset_id, "series": name,
                         "series_code": (codes or {}).get(name, str(i)), "period": period,
                         "period_start": _period_start(period), "frequency": frequency,
                         "value": value, "unit": unit})
    return pd.DataFrame(rows)


def record(series: dict[str, dict[str, float | None]], key: str = "singstat:T1", **kw) -> DatasetRecord:
    source_id, dataset_id = key.split(":", 1)
    df = frame(series, source_id=source_id, dataset_id=dataset_id, **kw)
    return DatasetRecord(key=key, source_id=source_id, dataset_id=dataset_id, title=f"Test table {dataset_id}",
                         frame=df, unit=kw.get("unit", "Thousand"), frequency=kw.get("frequency", "Annual"))


def make_ctx(*records: DatasetRecord, query: str = "test query") -> RunContext:
    ctx = RunContext(run_id="test-run", query=query)
    for r in records:
        ctx.add_dataset(r)
    return ctx


GROWTH = {"2020": 100.0, "2021": 110.0, "2022": 121.0, "2023": 133.1}  # +10% a year
TOTAL = {"2020": 1000.0, "2021": 1000.0, "2022": 1000.0, "2023": 1000.0}
