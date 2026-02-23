"""Shared SQLite repository helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from typing import Any


def now_iso() -> str:
    """Current UTC timestamp as ISO string."""

    return datetime.now(UTC).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    """Parse ISO datetime from DB."""

    if value is None:
        return None
    return datetime.fromisoformat(value)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert sqlite row to standard dictionary."""

    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def dumps_json(value: Any) -> str:
    """JSON serialization used by snapshots and pending payloads."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads_json(value: str | None) -> Any:
    """Safe json decode helper."""

    if value is None or value == "":
        return None
    return json.loads(value)

