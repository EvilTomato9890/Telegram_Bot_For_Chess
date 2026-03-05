"""SQLite repository for players."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from domain.exceptions import DomainError
from domain.models import Player, PlayerStatus
from infra.db import Database

from .common import parse_iso


class PlayerRepository:
    """Player persistence adapter."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def add(self, player: Player, connection: sqlite3.Connection | None = None) -> Player:
        sql = """
            INSERT INTO players(
                telegram_id, username, full_name, rating, status, score, buchholz,
                median_buchholz, sonneborn_berger, had_bye, current_board, seat_hint, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            player.telegram_id,
            player.username,
            player.full_name,
            player.rating,
            player.status.value,
            player.score,
            player.buchholz,
            player.median_buchholz,
            player.sonneborn_berger,
            1 if player.had_bye else 0,
            player.current_board,
            player.seat_hint,
            player.created_at.isoformat(),
        )
        if connection is not None:
            cursor = connection.execute(sql, params)
            row = connection.execute("SELECT * FROM players WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert player")
            return mapped
        with self._database.transaction() as conn:
            cursor = conn.execute(sql, params)
            row = conn.execute("SELECT * FROM players WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert player")
            return mapped

    def update(self, player: Player, connection: sqlite3.Connection | None = None) -> Player:
        if player.id is None:
            raise DomainError("player id is required")
        sql = """
            UPDATE players
            SET username = ?, full_name = ?, rating = ?, status = ?, score = ?, buchholz = ?,
                median_buchholz = ?, sonneborn_berger = ?, had_bye = ?, current_board = ?, seat_hint = ?
            WHERE id = ?
        """
        params = (
            player.username,
            player.full_name,
            player.rating,
            player.status.value,
            player.score,
            player.buchholz,
            player.median_buchholz,
            player.sonneborn_berger,
            1 if player.had_bye else 0,
            player.current_board,
            player.seat_hint,
            player.id,
        )
        if connection is not None:
            connection.execute(sql, params)
            row = connection.execute("SELECT * FROM players WHERE id = ?", (player.id,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("player not found")
            return mapped
        with self._database.transaction() as conn:
            conn.execute(sql, params)
            row = conn.execute("SELECT * FROM players WHERE id = ?", (player.id,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("player not found")
            return mapped

    def get_by_id(self, player_id: int, connection: sqlite3.Connection | None = None) -> Player | None:
        if connection is not None:
            return self._map_row(connection.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone())
        with self._database.transaction() as conn:
            return self._map_row(conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone())

    def get_by_telegram_id(
        self, telegram_id: int, connection: sqlite3.Connection | None = None
    ) -> Player | None:
        if connection is not None:
            return self._map_row(
                connection.execute("SELECT * FROM players WHERE telegram_id = ?", (telegram_id,)).fetchone()
            )
        with self._database.transaction() as conn:
            return self._map_row(conn.execute("SELECT * FROM players WHERE telegram_id = ?", (telegram_id,)).fetchone())

    def get_by_username(self, username: str, connection: sqlite3.Connection | None = None) -> Player | None:
        normalized = username.strip().removeprefix("@")
        if not normalized:
            return None
        if connection is not None:
            return self._map_row(connection.execute("SELECT * FROM players WHERE username = ?", (normalized,)).fetchone())
        with self._database.transaction() as conn:
            return self._map_row(conn.execute("SELECT * FROM players WHERE username = ?", (normalized,)).fetchone())

    def list_all(self, connection: sqlite3.Connection | None = None) -> list[Player]:
        if connection is not None:
            rows = connection.execute("SELECT * FROM players ORDER BY id ASC").fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute("SELECT * FROM players ORDER BY id ASC").fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def list_active(self, connection: sqlite3.Connection | None = None) -> list[Player]:
        if connection is not None:
            rows = connection.execute(
                "SELECT * FROM players WHERE status = ? ORDER BY score DESC, rating DESC, id ASC",
                (PlayerStatus.ACTIVE.value,),
            ).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM players WHERE status = ? ORDER BY score DESC, rating DESC, id ASC",
                (PlayerStatus.ACTIVE.value,),
            ).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def clear_all(self, connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM players")

    def delete_by_id(self, player_id: int, connection: sqlite3.Connection | None = None) -> bool:
        if connection is not None:
            cursor = connection.execute("DELETE FROM players WHERE id = ?", (player_id,))
            return cursor.rowcount > 0
        with self._database.transaction() as conn:
            cursor = conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
            return cursor.rowcount > 0

    @staticmethod
    def _map_row(row: sqlite3.Row | None) -> Player | None:
        if row is None:
            return None
        created_at = parse_iso(row["created_at"])
        if created_at is None:
            created_at = datetime.now(UTC)
        return Player(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            full_name=row["full_name"],
            rating=row["rating"],
            status=PlayerStatus(row["status"]),
            score=row["score"],
            buchholz=row["buchholz"],
            median_buchholz=row["median_buchholz"],
            sonneborn_berger=row["sonneborn_berger"],
            had_bye=bool(row["had_bye"]),
            current_board=row["current_board"],
            seat_hint=row["seat_hint"],
            created_at=created_at,
        )


