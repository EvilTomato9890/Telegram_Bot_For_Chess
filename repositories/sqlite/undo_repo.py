"""SQLite repository for undo snapshots."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from domain.exceptions import DomainError
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
                raise DomainError("failed to insert undo snapshot")
            return mapped
        with self._database.transaction() as conn:
            cursor = conn.execute(sql, params)
            row = conn.execute("SELECT * FROM undo_snapshots WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert undo snapshot")
            return mapped

    def get_last_unrestored(
        self,
        actor_telegram_id: int | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> UndoSnapshot | None:
        """Return latest unrestored snapshot, optionally scoped to one actor."""

        if actor_telegram_id is None:
            sql = "SELECT * FROM undo_snapshots WHERE restored_at IS NULL ORDER BY id DESC LIMIT 1"
            params: tuple[object, ...] = ()
        else:
            sql = """
                SELECT * FROM undo_snapshots
                WHERE restored_at IS NULL AND actor_telegram_id = ?
                ORDER BY id DESC
                LIMIT 1
            """
            params = (actor_telegram_id,)
        if connection is not None:
            return self._map_row(connection.execute(sql, params).fetchone())
        with self._database.transaction() as conn:
            return self._map_row(conn.execute(sql, params).fetchone())

    def mark_restored(self, snapshot_id: int, connection: sqlite3.Connection | None = None) -> None:
        restored_at = datetime.now(UTC).isoformat()
        if connection is not None:
            connection.execute("UPDATE undo_snapshots SET restored_at = ? WHERE id = ?", (restored_at, snapshot_id))
            return
        with self._database.transaction() as conn:
            conn.execute("UPDATE undo_snapshots SET restored_at = ? WHERE id = ?", (restored_at, snapshot_id))

    def delete_by_id(self, snapshot_id: int, connection: sqlite3.Connection | None = None) -> bool:
        """Delete snapshot row (used to cleanup failed pre-mutation attempts)."""

        if connection is not None:
            cursor = connection.execute("DELETE FROM undo_snapshots WHERE id = ?", (snapshot_id,))
            return cursor.rowcount > 0
        with self._database.transaction() as conn:
            cursor = conn.execute("DELETE FROM undo_snapshots WHERE id = ?", (snapshot_id,))
            return cursor.rowcount > 0

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



