"""SQLite repository for player reports."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from domain.exceptions import DomainError
from domain.models import GameReport, GameResult
from infra.db import Database

from .common import parse_iso


class GameReportRepository:
    """Store per-player game reports with overwrite semantics."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def upsert(
        self,
        game_id: int,
        reporter_player_id: int,
        reported_result: GameResult,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> GameReport:
        sql = """
            INSERT INTO game_reports(game_id, reporter_player_id, reported_result, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(game_id, reporter_player_id) DO UPDATE SET
                reported_result = excluded.reported_result,
                created_at = excluded.created_at
        """
        now = datetime.now(UTC).isoformat()
        params = (game_id, reporter_player_id, reported_result.value, now)
        fetch_sql = "SELECT * FROM game_reports WHERE game_id = ? AND reporter_player_id = ?"
        if connection is not None:
            connection.execute(sql, params)
            row = connection.execute(fetch_sql, (game_id, reporter_player_id)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to upsert report")
            return mapped
        with self._database.transaction() as conn:
            conn.execute(sql, params)
            row = conn.execute(fetch_sql, (game_id, reporter_player_id)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to upsert report")
            return mapped

    def list_by_game(self, game_id: int, connection: sqlite3.Connection | None = None) -> list[GameReport]:
        sql = "SELECT * FROM game_reports WHERE game_id = ? ORDER BY reporter_player_id ASC"
        if connection is not None:
            rows = connection.execute(sql, (game_id,)).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute(sql, (game_id,)).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def delete_by_game(self, game_id: int, connection: sqlite3.Connection | None = None) -> None:
        if connection is not None:
            connection.execute("DELETE FROM game_reports WHERE game_id = ?", (game_id,))
            return
        with self._database.transaction() as conn:
            conn.execute("DELETE FROM game_reports WHERE game_id = ?", (game_id,))

    def clear_all(self, connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM game_reports")

    @staticmethod
    def _map_row(row: sqlite3.Row | None) -> GameReport | None:
        if row is None:
            return None
        created_at = parse_iso(row["created_at"]) or datetime.now(UTC)
        return GameReport(
            id=row["id"],
            game_id=row["game_id"],
            reporter_player_id=row["reporter_player_id"],
            reported_result=GameResult(row["reported_result"]),
            created_at=created_at,
        )



