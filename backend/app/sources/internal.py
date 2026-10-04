"""Mock internal systems (synthetic data in the app database, SQL access)."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select

from app.core.chaos import chaos
from app.core.models import CANONICAL_COLUMNS, DatasetRecord
from app.db.models import InternalGrantDisbursement, InternalProgrammeEnrolment
from app.db.session import SessionLocal
from app.sources.base import SourceError, parse_period

SOURCE_ID = "internal"

TABLES = {
    "programme_enrolments": {
        "model": InternalProgrammeEnrolment,
        "title": "Workforce programme outcomes by sector (internal, synthetic)",
        "measures": {"enrolled": "Persons", "completed": "Persons", "placed_in_jobs": "Persons"},
        "description": "Annual enrolments, completions and job placements of workforce training programmes by sector.",
    },
    "grant_disbursements": {
        "model": InternalGrantDisbursement,
        "title": "Grant disbursements by sector (internal, synthetic)",
        "measures": {"amount_sgd_m": "S$ million", "firms_supported": "Number"},
        "description": "Annual grant amounts and firms supported by sector and scheme.",
    },
}


class InternalAdapter:
    def catalogue(self) -> list[dict[str, str]]:
        return [{"table": name, "title": t["title"], "description": t["description"],
                 "measures": ", ".join(t["measures"])} for name, t in TABLES.items()]

    async def fetch(self, table: str, sectors: list[str] | None = None,
                    start_year: int | None = None, end_year: int | None = None) -> DatasetRecord:
        chaos.check_source(SOURCE_ID)
        if table not in TABLES:
            raise SourceError(f"Unknown internal table '{table}'. Available: {', '.join(TABLES)}")
        spec = TABLES[table]
        model = spec["model"]
        stmt = select(model)
        if sectors:
            stmt = stmt.where(model.sector.in_(sectors))
        if start_year:
            stmt = stmt.where(model.year >= start_year)
        if end_year:
            stmt = stmt.where(model.year <= end_year)
        async with SessionLocal() as session:
            rows = (await session.scalars(stmt)).all()
        raw = pd.DataFrame([{c.name: getattr(r, c.name) for c in model.__table__.columns} for r in rows])
        records = []
        if not raw.empty:
            grouped = raw.groupby(["year", "sector"], as_index=False)[list(spec["measures"])].sum()
            for _, row in grouped.iterrows():
                label, start, freq = parse_period(int(row["year"]))
                for measure, unit in spec["measures"].items():
                    records.append({
                        "source_id": SOURCE_ID, "dataset_id": table,
                        "series": f"{row['sector']} - {measure.replace('_', ' ')}", "series_code": measure,
                        "period": label, "period_start": start, "frequency": freq,
                        "value": float(row[measure]), "unit": unit,
                    })
        frame = pd.DataFrame.from_records(records, columns=CANONICAL_COLUMNS)
        return DatasetRecord(
            key=f"{SOURCE_ID}:{table}", source_id=SOURCE_ID, dataset_id=table, title=spec["title"],
            url=None, unit=None, frequency="Annual", trust_tier=1,
            notes=["Synthetic data generated for the mock internal system (not official statistics)."],
            data_source_agency="Internal system (mock)", frame=frame,
        )


internal = InternalAdapter()
