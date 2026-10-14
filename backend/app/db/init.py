"""Create tables and seed the synthetic internal-system data.

Run as a one-off: ``python -m app.db.init`` (also the ECS migration task). Idempotent.
Schema changes after the deadline would move to Alembic migrations.
"""

import asyncio
import random
import uuid

from sqlalchemy import func, inspect, select, text

from app.db.models import Analysis, Base, Chat, InternalGrantDisbursement, InternalProgrammeEnrolment
from app.db.session import SessionLocal, engine

SECTORS = {
    # sector: (base enrolment in 2019, annual growth)
    "Information And Communications": (5200, 0.11),
    "Financial And Insurance Services": (3900, 0.05),
    "Manufacturing": (4600, 0.01),
    "Professional Services": (3100, 0.06),
    "Wholesale And Retail Trade": (2800, -0.01),
    "Accommodation And Food Services": (2300, 0.02),
}
PROGRAMMES = ["Career Conversion Programme", "Skills Upgrading Track"]
SCHEMES = ["Productivity Grant", "Digitalisation Grant"]


ANALYSIS_NEW_COLUMNS = {"chat_id": "VARCHAR(36)", "turn": "INTEGER DEFAULT 1", "version": "INTEGER DEFAULT 1"}


def _add_missing_columns(conn) -> None:
    """create_all never alters an existing table; add the chat columns to databases from before chats."""
    existing = {c["name"] for c in inspect(conn).get_columns("analyses")}
    for name, ddl in ANALYSIS_NEW_COLUMNS.items():
        if name not in existing:
            conn.execute(text(f"ALTER TABLE analyses ADD COLUMN {name} {ddl}"))


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
    await backfill_chats()


async def backfill_chats() -> int:
    """Every analysis from before chats existed becomes a one-question chat. Idempotent."""
    async with SessionLocal() as session:
        orphans = (await session.scalars(select(Analysis).where(Analysis.chat_id.is_(None)))).all()
        for a in orphans:
            chat = Chat(id=str(uuid.uuid4()), title=a.query.strip()[:80], created_at=a.created_at,
                        updated_at=a.finished_at or a.created_at)
            session.add(chat)
            a.chat_id, a.turn, a.version = chat.id, 1, 1
        await session.commit()
        return len(orphans)


async def seed_internal() -> int:
    """Deterministic synthetic data (seeded RNG) so demo numbers are reproducible."""
    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(InternalProgrammeEnrolment))
        if existing:
            return 0
        rng = random.Random(42)
        rows: list = []
        for sector, (base, growth) in SECTORS.items():
            for year in range(2019, 2026):
                covid = 0.82 if year == 2020 else 1.0
                level = base * (1 + growth) ** (year - 2019) * covid
                for share, programme in zip((0.6, 0.4), PROGRAMMES, strict=True):
                    enrolled = int(level * share * rng.uniform(0.95, 1.05))
                    completed = int(enrolled * rng.uniform(0.78, 0.9))
                    placed = int(completed * rng.uniform(0.62, 0.8))
                    rows.append(InternalProgrammeEnrolment(year=year, sector=sector, programme=programme,
                                                           enrolled=enrolled, completed=completed,
                                                           placed_in_jobs=placed))
                for scheme in SCHEMES:
                    amount = round(level / 100 * rng.uniform(0.8, 1.2), 1)
                    rows.append(InternalGrantDisbursement(year=year, sector=sector, scheme=scheme,
                                                          amount_sgd_m=amount,
                                                          firms_supported=int(amount * rng.uniform(8, 14))))
        session.add_all(rows)
        await session.commit()
        return len(rows)


async def main() -> None:
    await create_schema()
    seeded = await seed_internal()
    print(f"schema ready; seeded {seeded} internal rows")


if __name__ == "__main__":
    asyncio.run(main())
