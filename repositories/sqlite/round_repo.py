"""SQLite repository for rounds."""

from __future__ import annotations

from domain.exceptions import DomainError

from datetime import UTC, datetime
import sqlite3

from domain.models import Round, RoundStatus
from infra.db import Database

from .common import parse_iso


class RoundRepository:
    """Round persistence adapter."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def add(self, round_: Round, connection: sqlite3.Connection | None = None) -> Round:
        sql = """
            INSERT INTO rounds(number, status, starts_at, window_end_at, generated_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            round_.number,
            round_.status.value,
            round_.starts_at.isoformat() if round_.starts_at else None,
            round_.window_end_at.isoformat() if round_.window_end_at else None,
            round_.generated_at.isoformat(),
            round_.closed_at.isoformat() if round_.closed_at else None,
        )
        if connection is not None:
            cursor = connection.execute(sql, params)
            row = connection.execute("SELECT * FROM rounds WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert round")
            return mapped
        with self._database.transaction() as conn:
            cursor = conn.execute(sql, params)
            row = conn.execute("SELECT * FROM rounds WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert round")
            return mapped

    def update(self, round_: Round, connection: sqlite3.Connection | None = None) -> Round:
        if round_.id is None:
            raise DomainError("round id is required")
        sql = """
            UPDATE rounds
            SET number = ?, status = ?, starts_at = ?, window_end_at = ?, generated_at = ?, closed_at = ?
            WHERE id = ?
        """
        params = (
            round_.number,
            round_.status.value,
            round_.starts_at.isoformat() if round_.starts_at else None,
            round_.window_end_at.isoformat() if round_.window_end_at else None,
            round_.generated_at.isoformat(),
            round_.closed_at.isoformat() if round_.closed_at else None,
            round_.id,
        )
        if connection is not None:
            connection.execute(sql, params)
            row = connection.execute("SELECT * FROM rounds WHERE id = ?", (round_.id,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("round not found")
            return mapped
        with self._database.transaction() as conn:
            conn.execute(sql, params)
            row = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_.id,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("round not found")
            return mapped

    def get_by_id(self, round_id: int, connection: sqlite3.Connection | None = None) -> Round | None:
        if connection is not None:
            row = connection.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
            return self._map_row(row)
        with self._database.transaction() as conn:
            row = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
            return self._map_row(row)

    def get_by_number(self, number: int, connection: sqlite3.Connection | None = None) -> Round | None:
        if connection is not None:
            row = connection.execute("SELECT * FROM rounds WHERE number = ?", (number,)).fetchone()
            return self._map_row(row)
        with self._database.transaction() as conn:
            row = conn.execute("SELECT * FROM rounds WHERE number = ?", (number,)).fetchone()
            return self._map_row(row)

    def get_current(self, connection: sqlite3.Connection | None = None) -> Round | None:
        sql = "SELECT * FROM rounds WHERE status IN (?, ?) ORDER BY number DESC LIMIT 1"
        params = (RoundStatus.GENERATED.value, RoundStatus.ONGOING.value)
        if connection is not None:
            row = connection.execute(sql, params).fetchone()
            return self._map_row(row)
        with self._database.transaction() as conn:
            row = conn.execute(sql, params).fetchone()
            return self._map_row(row)

    def list_all(self, connection: sqlite3.Connection | None = None) -> list[Round]:
        if connection is not None:
            rows = connection.execute("SELECT * FROM rounds ORDER BY number ASC").fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute("SELECT * FROM rounds ORDER BY number ASC").fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def clear_all(self, connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM rounds")

    @staticmethod
    def _map_row(row: sqlite3.Row | None) -> Round | None:
        if row is None:
            return None
        generated_at = parse_iso(row["generated_at"])
        if generated_at is None:
            generated_at = datetime.now(UTC)
        return Round(
            id=row["id"],
            number=row["number"],
            status=RoundStatus(row["status"]),
            starts_at=parse_iso(row["starts_at"]),
            window_end_at=parse_iso(row["window_end_at"]),
            generated_at=generated_at,
            closed_at=parse_iso(row["closed_at"]),
        )



