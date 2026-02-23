"""SQLite repository for undo snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
import sqlite3

from domain.models import UndoSnapshot
from infra.db import Database

from .common import parse_iso


class UndoRepository:
    """Store and load organizer action snapshots."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def add(self, snapshot: UndoSnapshot, connection: sqlite3.Connection | None = None) -> UndoSnapshot:
        sql = """
            INSERT INTO undo_snapshots(actor_telegram_id, action_name, snapshot_json, created_at, restored_at)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (
            snapshot.actor_telegram_id,
            snapshot.action_name,
            snapshot.snapshot_json,
            snapshot.created_at.isoformat(),
            snapshot.restored_at.isoformat() if snapshot.restored_at else None,
        )
        if connection is not None:
            cursor = connection.execute(sql, params)
            row = connection.execute("SELECT * FROM undo_snapshots WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise ValueError("failed to insert undo snapshot")
            return mapped
        with self._database.transaction() as conn:
            cursor = conn.execute(sql, params)
            row = conn.execute("SELECT * FROM undo_snapshots WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise ValueError("failed to insert undo snapshot")
            return mapped

    def get_last_unrestored(self, connection: sqlite3.Connection | None = None) -> UndoSnapshot | None:
        sql = "SELECT * FROM undo_snapshots WHERE restored_at IS NULL ORDER BY id DESC LIMIT 1"
        if connection is not None:
            return self._map_row(connection.execute(sql).fetchone())
        with self._database.transaction() as conn:
            return self._map_row(conn.execute(sql).fetchone())

    def mark_restored(self, snapshot_id: int, connection: sqlite3.Connection | None = None) -> None:
        restored_at = datetime.now(UTC).isoformat()
        if connection is not None:
            connection.execute("UPDATE undo_snapshots SET restored_at = ? WHERE id = ?", (restored_at, snapshot_id))
            return
        with self._database.transaction() as conn:
            conn.execute("UPDATE undo_snapshots SET restored_at = ? WHERE id = ?", (restored_at, snapshot_id))

    @staticmethod
    def _map_row(row: sqlite3.Row | None) -> UndoSnapshot | None:
        if row is None:
            return None
        created_at = parse_iso(row["created_at"]) or datetime.now(UTC)
        return UndoSnapshot(
            id=row["id"],
            actor_telegram_id=row["actor_telegram_id"],
            action_name=row["action_name"],
            snapshot_json=row["snapshot_json"],
            created_at=created_at,
            restored_at=parse_iso(row["restored_at"]),
        )

