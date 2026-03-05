"""SQLite repository for board tables."""

from __future__ import annotations

import sqlite3

from domain.exceptions import DomainError
from domain.models import Table
from infra.db import Database


class TableRepository:
    """Table persistence adapter."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def add(self, table: Table, connection: sqlite3.Connection | None = None) -> Table:
        sql = "INSERT INTO tables(number, location, place_hint) VALUES (?, ?, ?)"
        params = (table.number, table.location, table.place_hint)
        if connection is not None:
            try:
                cursor = connection.execute(sql, params)
            except sqlite3.IntegrityError as exc:
                raise DomainError(f"Стол с номером {table.number} уже существует.") from exc
            row = connection.execute("SELECT * FROM tables WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("Не удалось добавить стол.")
            return mapped
        with self._database.transaction() as conn:
            try:
                cursor = conn.execute(sql, params)
            except sqlite3.IntegrityError as exc:
                raise DomainError(f"Стол с номером {table.number} уже существует.") from exc
            row = conn.execute("SELECT * FROM tables WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("Не удалось добавить стол.")
            return mapped

    def remove_by_number(self, number: int, connection: sqlite3.Connection | None = None) -> bool:
        if connection is not None:
            cursor = connection.execute("DELETE FROM tables WHERE number = ?", (number,))
            return cursor.rowcount > 0
        with self._database.transaction() as conn:
            cursor = conn.execute("DELETE FROM tables WHERE number = ?", (number,))
            return cursor.rowcount > 0

    def list_all(self, connection: sqlite3.Connection | None = None) -> list[Table]:
        if connection is not None:
            rows = connection.execute("SELECT * FROM tables ORDER BY number ASC").fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute("SELECT * FROM tables ORDER BY number ASC").fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def get_by_number(self, number: int, connection: sqlite3.Connection | None = None) -> Table | None:
        if connection is not None:
            return self._map_row(connection.execute("SELECT * FROM tables WHERE number = ?", (number,)).fetchone())
        with self._database.transaction() as conn:
            return self._map_row(conn.execute("SELECT * FROM tables WHERE number = ?", (number,)).fetchone())

    def clear_all(self, connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM tables")

    @staticmethod
    def _map_row(row: sqlite3.Row | None) -> Table | None:
        if row is None:
            return None
        return Table(
            id=row["id"],
            number=row["number"],
            location=row["location"],
            place_hint=row["place_hint"],
        )



