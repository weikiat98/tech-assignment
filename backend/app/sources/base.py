"""Shared plumbing for source adapters: snapshots, retries, period parsing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from tenacity import AsyncRetrying, retry_if_not_exception_type, stop_after_attempt, wait_exponential_jitter

from app.config import get_settings
from app.core.chaos import ChaosError
from app.core.models import CANONICAL_COLUMNS


class SourceError(RuntimeError):
    """A source could not deliver data (after retries and fallbacks)."""


class SnapshotStore:
    """File-backed store of raw source responses.

    Every successful live call is recorded; when a source fails (or offline mode is
    on) the adapter replays the latest recording. The same files serve as test fixtures.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or get_settings().snapshot_dir)

    @staticmethod
    def key_for(*parts: Any) -> str:
        raw = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _path(self, source_id: str, name: str, key: str, ext: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:60]
        return self.root / source_id / f"{safe}__{key}.{ext}"

    def save_json(self, source_id: str, name: str, key: str, payload: Any) -> Path:
        path = self._path(source_id, name, key, "json")
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"recorded_at": datetime.now(UTC).isoformat(), "payload": payload}
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        return path

    def load_json(self, source_id: str, name: str, key: str) -> tuple[Any, str] | None:
        path = self._path(source_id, name, key, "json")
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        return record["payload"], record.get("recorded_at", "unknown")

    def save_bytes(self, source_id: str, name: str, key: str, data: bytes, ext: str) -> Path:
        path = self._path(source_id, name, key, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def load_bytes(self, source_id: str, name: str, key: str, ext: str) -> tuple[bytes, str] | None:
        path = self._path(source_id, name, key, ext)
        if not path.exists():
            return None
        recorded = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
        return path.read_bytes(), recorded


snapshots = SnapshotStore()
_source_semaphore = asyncio.Semaphore(get_settings().source_max_concurrency)


class SourceBreaker:
    """Per-transport circuit breaker shared across runs.

    After ``threshold`` consecutive failed calls (each already retried), the transport is skipped
    for ``open_seconds`` so the adapter goes straight to its fallback instead of hammering a
    server that is down or rate-limiting us. A 403/429 opens it immediately.
    """

    def __init__(self, threshold: int = 2, open_seconds: float = 120.0) -> None:
        self.threshold, self.open_seconds = threshold, open_seconds
        self.failures = 0
        self.open_until = 0.0

    @property
    def is_open(self) -> bool:
        return time.monotonic() < self.open_until

    def record(self, ok: bool, blocked: bool = False) -> None:
        if ok:
            self.failures, self.open_until = 0, 0.0
            return
        self.failures += 1
        if blocked or self.failures >= self.threshold:
            self.open_until = time.monotonic() + self.open_seconds

    def reset(self) -> None:
        self.failures, self.open_until = 0, 0.0


def looks_blocked(exc: BaseException) -> bool:
    """True for errors that mean 'stop calling for a while' (403 / 429), including inside ExceptionGroups."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (403, 429):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(looks_blocked(e) for e in exc.exceptions)
    text = str(exc)
    return any(s in text for s in ("403", "429", "Forbidden", "Too Many Requests"))


async def with_retries(fn, *args, attempts: int = 3, **kwargs):
    """Run an async callable with exponential backoff + jitter, bounded by a global concurrency limit."""
    async with _source_semaphore:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential_jitter(initial=0.5, max=4),
            retry=retry_if_not_exception_type(ChaosError),  # a simulated outage is deterministic
            reraise=True,
        ):
            with attempt:
                return await fn(*args, **kwargs)


# --- period handling ----------------------------------------------------------------

_QUARTER = re.compile(r"^(\d{4})\s*-?\s*(?:Q|\s)([1-4])$", re.I)
_QUARTER_ALT = re.compile(r"^(\d{4})\s+([1-4])Q$", re.I)
_MONTH = re.compile(r"^(\d{4})[-\s]?(\d{1,2}|[A-Za-z]{3})$")
_YEAR = re.compile(r"^(\d{4})$")
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                       "oct", "nov", "dec"], start=1)}


def parse_period(raw: Any) -> tuple[str, date, str] | None:
    """Parse a period label into (normalised label, start date, frequency)."""
    text = str(raw).strip()
    if m := _YEAR.match(text):
        y = int(m.group(1))
        return str(y), date(y, 1, 1), "Annual"
    if (m := _QUARTER.match(text)) or (m := _QUARTER_ALT.match(text)):
        y, q = int(m.group(1)), int(m.group(2))
        return f"{y}-Q{q}", date(y, 3 * (q - 1) + 1, 1), "Quarterly"
    if m := _MONTH.match(text):
        y, mo = int(m.group(1)), m.group(2)
        month = int(mo) if mo.isdigit() else _MONTHS.get(mo.lower()[:3])
        if month and 1 <= month <= 12:
            return f"{y}-{month:02d}", date(y, month, 1), "Monthly"
    return None


_MISSING_MARKERS = {"", "na", "n.a.", "-", "--", "nil", "s", "x", "..", "none", "null"}


def parse_value(raw: Any) -> tuple[float | None, list[str]]:
    """Parse a numeric cell, handling footnote markers. Returns (value, notes)."""
    if raw is None:
        return None, []
    if isinstance(raw, int | float) and not pd.isna(raw):
        return float(raw), []
    text = str(raw).strip()
    notes = []
    if text.lower() in _MISSING_MARKERS:
        return None, [f"missing marker '{text}'"]
    if text.endswith(("p", "P")) and text[:-1].replace(",", "").replace(".", "", 1).lstrip("-").isdigit():
        notes.append("provisional value")
        text = text[:-1]
    text = text.replace(",", "").replace("$", "").replace("%", "").strip()
    try:
        return float(text), notes
    except ValueError:
        return None, [f"unparseable value '{raw}'"]


def empty_canonical() -> pd.DataFrame:
    return pd.DataFrame(columns=CANONICAL_COLUMNS)


def year_filter(frame: pd.DataFrame, start_year: int | None, end_year: int | None) -> pd.DataFrame:
    if frame.empty:
        return frame
    years = pd.to_datetime(frame["period_start"]).dt.year
    mask = pd.Series(True, index=frame.index)
    if start_year:
        mask &= years >= start_year
    if end_year:
        mask &= years <= end_year
    return frame[mask]
