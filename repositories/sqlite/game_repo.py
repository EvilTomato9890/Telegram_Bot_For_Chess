"""SQLite repository for games."""

from __future__ import annotations

from domain.exceptions import DomainError

from datetime import UTC, datetime
import sqlite3

from domain.models import Game, GameResult
from infra.db import Database

from .common import parse_iso


class GameRepository:
    """Game persistence adapter."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def add(self, game: Game, connection: sqlite3.Connection | None = None) -> Game:
        sql = """
            INSERT INTO games(
                round_id, board_number, white_player_id, black_player_id, result, result_source,
                is_bye, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            game.round_id,
            game.board_number,
            game.white_player_id,
            game.black_player_id,
            game.result.value if game.result else None,
            game.result_source,
            1 if game.is_bye else 0,
            game.created_at.isoformat(),
            game.updated_at.isoformat(),
        )
        if connection is not None:
            cursor = connection.execute(sql, params)
            row = connection.execute("SELECT * FROM games WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert game")
            return mapped
        with self._database.transaction() as conn:
            cursor = conn.execute(sql, params)
            row = conn.execute("SELECT * FROM games WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert game")
            return mapped

    def update(self, game: Game, connection: sqlite3.Connection | None = None) -> Game:
        if game.id is None:
            raise DomainError("game id is required")
        sql = """
            UPDATE games
            SET round_id = ?, board_number = ?, white_player_id = ?, black_player_id = ?, result = ?,
                result_source = ?, is_bye = ?, updated_at = ?
            WHERE id = ?
        """
        params = (
            game.round_id,
            game.board_number,
            game.white_player_id,
            game.black_player_id,
            game.result.value if game.result else None,
            game.result_source,
            1 if game.is_bye else 0,
            game.updated_at.isoformat(),
            game.id,
        )
        if connection is not None:
            connection.execute(sql, params)
            row = connection.execute("SELECT * FROM games WHERE id = ?", (game.id,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("game not found")
            return mapped
        with self._database.transaction() as conn:
            conn.execute(sql, params)
            row = conn.execute("SELECT * FROM games WHERE id = ?", (game.id,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("game not found")
            return mapped

    def get_by_id(self, game_id: int, connection: sqlite3.Connection | None = None) -> Game | None:
        if connection is not None:
            return self._map_row(connection.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone())
        with self._database.transaction() as conn:
            return self._map_row(conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone())

    def list_by_round(self, round_id: int, connection: sqlite3.Connection | None = None) -> list[Game]:
        if connection is not None:
            rows = connection.execute(
                "SELECT * FROM games WHERE round_id = ? ORDER BY board_number ASC",
                (round_id,),
            ).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM games WHERE round_id = ? ORDER BY board_number ASC",
                (round_id,),
            ).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def list_all(self, connection: sqlite3.Connection | None = None) -> list[Game]:
        if connection is not None:
            rows = connection.execute("SELECT * FROM games ORDER BY id ASC").fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute("SELECT * FROM games ORDER BY id ASC").fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def list_by_player(self, player_id: int, connection: sqlite3.Connection | None = None) -> list[Game]:
        sql = """
            SELECT * FROM games
            WHERE white_player_id = ? OR black_player_id = ?
            ORDER BY id DESC
        """
        if connection is not None:
            rows = connection.execute(sql, (player_id, player_id)).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute(sql, (player_id, player_id)).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def clear_all(self, connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM games")

    @staticmethod
    def _map_row(row: sqlite3.Row | None) -> Game | None:
        if row is None:
            return None
        created_at = parse_iso(row["created_at"]) or datetime.now(UTC)
        updated_at = parse_iso(row["updated_at"]) or created_at
        result_value = row["result"]
        return Game(
            id=row["id"],
            round_id=row["round_id"],
            board_number=row["board_number"],
            white_player_id=row["white_player_id"],
            black_player_id=row["black_player_id"],
            result=GameResult(result_value) if result_value else None,
            result_source=row["result_source"],
            is_bye=bool(row["is_bye"]),
            created_at=created_at,
            updated_at=updated_at,
        )



