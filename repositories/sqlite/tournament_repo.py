"""SQLite repository for tournament state."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import sqlite3

from domain.models import Tournament, TournamentStatus
from infra.db import Database

from .common import parse_iso


class TournamentRepository:
    """CRUD for the single tournament row."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, connection: sqlite3.Connection | None = None) -> Tournament | None:
        if connection is not None:
            row = connection.execute("SELECT * FROM tournaments WHERE id = 1").fetchone()
            return self._map_row(row)
        with self._database.transaction() as conn:
            row = conn.execute("SELECT * FROM tournaments WHERE id = 1").fetchone()
            return self._map_row(row)

    def upsert(self, tournament: Tournament, connection: sqlite3.Connection | None = None) -> Tournament:
        sql = """
            INSERT INTO tournaments(
                id, status, number_of_rounds, current_round, rules_text, prepared,
                pending_pairing_payload, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                number_of_rounds = excluded.number_of_rounds,
                current_round = excluded.current_round,
                rules_text = excluded.rules_text,
                prepared = excluded.prepared,
                pending_pairing_payload = excluded.pending_pairing_payload,
                updated_at = excluded.updated_at
        """
        created = tournament.created_at.isoformat()
        updated = datetime.now(UTC).isoformat()
        params = (
            1,
            tournament.status.value,
            tournament.number_of_rounds,
            tournament.current_round,
            tournament.rules_text,
            1 if tournament.prepared else 0,
            tournament.pending_pairing_payload,
            created,
            updated,
        )
        if connection is not None:
            connection.execute(sql, params)
            row = connection.execute("SELECT * FROM tournaments WHERE id = 1").fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise ValueError("failed to upsert tournament")
            return mapped
        with self._database.transaction() as conn:
            conn.execute(sql, params)
            row = conn.execute("SELECT * FROM tournaments WHERE id = 1").fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise ValueError("failed to upsert tournament")
            return mapped

    def ensure_exists(self, *, default_rules: str) -> Tournament:
        existing = self.get()
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        return self.upsert(
            Tournament(
                id=1,
                status=TournamentStatus.DRAFT,
                number_of_rounds=0,
                current_round=0,
                rules_text=default_rules,
                prepared=False,
                pending_pairing_payload=None,
                created_at=now,
                updated_at=now,
            )
        )

    @staticmethod
    def _map_row(row: sqlite3.Row | None) -> Tournament | None:
        if row is None:
            return None
        created = parse_iso(row["created_at"])
        updated = parse_iso(row["updated_at"])
        if created is None or updated is None:
            raise ValueError("corrupt tournament timestamps")
        return Tournament(
            id=row["id"],
            status=TournamentStatus(row["status"]),
            number_of_rounds=row["number_of_rounds"],
            current_round=row["current_round"],
            rules_text=row["rules_text"],
            prepared=bool(row["prepared"]),
            pending_pairing_payload=row["pending_pairing_payload"],
            created_at=created,
            updated_at=updated,
        )

    def update_status(
        self,
        status: TournamentStatus,
        *,
        prepared: bool | None = None,
        current_round: int | None = None,
        number_of_rounds: int | None = None,
        rules_text: str | None = None,
        pending_pairing_payload: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> Tournament:
        tournament = self.get(connection=connection)
        if tournament is None:
            raise ValueError("tournament is not initialized")
        updated = replace(
            tournament,
            status=status,
            prepared=tournament.prepared if prepared is None else prepared,
            current_round=tournament.current_round if current_round is None else current_round,
            number_of_rounds=tournament.number_of_rounds if number_of_rounds is None else number_of_rounds,
            rules_text=tournament.rules_text if rules_text is None else rules_text,
            pending_pairing_payload=pending_pairing_payload,
        )
        return self.upsert(updated, connection=connection)
