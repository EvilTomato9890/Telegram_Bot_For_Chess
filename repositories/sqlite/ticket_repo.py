"""SQLite repository for tickets."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Iterator

from domain.exceptions import DomainError
from domain.models import Ticket, TicketStatus, TicketType
from infra.db import Database

from .common import parse_iso


class TicketRepository:
    """Ticket persistence adapter with queue metrics."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Expose DB transaction scope for compound ticket operations."""

        with self._database.transaction() as conn:
            yield conn

    def add(self, ticket: Ticket, connection: sqlite3.Connection | None = None) -> Ticket:
        sql = """
            INSERT INTO tickets(
                type,
                author_telegram_id,
                status,
                assignee_telegram_id,
                game_id,
                description,
                opened_at,
                closed_at,
                closed_by_telegram_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            ticket.ticket_type.value,
            ticket.author_telegram_id,
            ticket.status.value,
            ticket.assignee_telegram_id,
            ticket.game_id,
            ticket.description,
            ticket.opened_at.isoformat(),
            ticket.closed_at.isoformat() if ticket.closed_at else None,
            ticket.closed_by_telegram_id,
        )
        if connection is not None:
            cursor = connection.execute(sql, params)
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert ticket")
            return mapped
        with self._database.transaction() as conn:
            cursor = conn.execute(sql, params)
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (cursor.lastrowid,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("failed to insert ticket")
            return mapped

    def update(self, ticket: Ticket, connection: sqlite3.Connection | None = None) -> Ticket:
        if ticket.id is None:
            raise DomainError("ticket id is required")
        sql = """
            UPDATE tickets
            SET type = ?, author_telegram_id = ?, status = ?, assignee_telegram_id = ?, game_id = ?,
                description = ?, opened_at = ?, closed_at = ?, closed_by_telegram_id = ?
            WHERE id = ?
        """
        params = (
            ticket.ticket_type.value,
            ticket.author_telegram_id,
            ticket.status.value,
            ticket.assignee_telegram_id,
            ticket.game_id,
            ticket.description,
            ticket.opened_at.isoformat(),
            ticket.closed_at.isoformat() if ticket.closed_at else None,
            ticket.closed_by_telegram_id,
            ticket.id,
        )
        if connection is not None:
            connection.execute(sql, params)
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket.id,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("ticket not found")
            return mapped
        with self._database.transaction() as conn:
            conn.execute(sql, params)
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket.id,)).fetchone()
            mapped = self._map_row(row)
            if mapped is None:
                raise DomainError("ticket not found")
            return mapped

    def get_by_id(self, ticket_id: int, connection: sqlite3.Connection | None = None) -> Ticket | None:
        if connection is not None:
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return self._map_row(row)
        with self._database.transaction() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return self._map_row(row)

    def list_open_by_author(self, author_telegram_id: int, connection: sqlite3.Connection | None = None) -> list[Ticket]:
        sql = """
            SELECT * FROM tickets
            WHERE author_telegram_id = ? AND status IN (?, ?)
            ORDER BY id DESC
        """
        params = (author_telegram_id, TicketStatus.OPEN.value, TicketStatus.ASSIGNED.value)
        if connection is not None:
            rows = connection.execute(sql, params).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def list_active(
        self,
        *,
        ticket_type: TicketType | None = None,
        assignee_telegram_id: int | None = None,
        include_unassigned: bool = True,
        connection: sqlite3.Connection | None = None,
    ) -> list[Ticket]:
        """Return active tickets filtered by type and assignee."""

        clauses = ["status IN (?, ?)"]
        params: list[object] = [TicketStatus.OPEN.value, TicketStatus.ASSIGNED.value]

        if ticket_type is not None:
            clauses.append("type = ?")
            params.append(ticket_type.value)

        if assignee_telegram_id is not None:
            if include_unassigned:
                clauses.append("(assignee_telegram_id = ? OR assignee_telegram_id IS NULL)")
            else:
                clauses.append("assignee_telegram_id = ?")
            params.append(assignee_telegram_id)

        where_sql = " AND ".join(clauses)
        sql = (
            "SELECT * FROM tickets "
            f"WHERE {where_sql} "
            "ORDER BY CASE status WHEN 'assigned' THEN 0 ELSE 1 END, id ASC"
        )
        if connection is not None:
            rows = connection.execute(sql, tuple(params)).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]
        with self._database.transaction() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [mapped for row in rows if (mapped := self._map_row(row)) is not None]

    def active_stats_for_assignee(self, assignee_telegram_id: int, connection: sqlite3.Connection | None = None) -> tuple[int, int]:
        sql = """
            SELECT
                SUM(CASE WHEN status IN (?, ?) THEN 1 ELSE 0 END) AS total_active,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS assigned_count
            FROM tickets
            WHERE assignee_telegram_id = ?
        """
        params = (
            TicketStatus.OPEN.value,
            TicketStatus.ASSIGNED.value,
            TicketStatus.ASSIGNED.value,
            assignee_telegram_id,
        )
        if connection is not None:
            row = connection.execute(sql, params).fetchone()
        else:
            with self._database.transaction() as conn:
                row = conn.execute(sql, params).fetchone()
        if row is None:
            return (0, 0)
        return (row["total_active"] or 0, row["assigned_count"] or 0)

    def clear_all(self, connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM tickets")

    @staticmethod
    def _map_row(row: sqlite3.Row | None) -> Ticket | None:
        if row is None:
            return None
        opened_at = parse_iso(row["opened_at"]) or datetime.now(UTC)
        return Ticket(
            id=row["id"],
            ticket_type=TicketType(row["type"]),
            author_telegram_id=row["author_telegram_id"],
            status=TicketStatus(row["status"]),
            assignee_telegram_id=row["assignee_telegram_id"],
            game_id=row["game_id"],
            description=row["description"],
            opened_at=opened_at,
            closed_at=parse_iso(row["closed_at"]),
            closed_by_telegram_id=row["closed_by_telegram_id"],
        )

