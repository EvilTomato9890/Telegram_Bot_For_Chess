"""SQLite repository for runtime role grants/revokes."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from domain.models import Role
from infra.db import Database


class RoleGrantRepository:
    """Append-only role change log repository."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def append(self, telegram_id: int, role: Role, source: str, connection: sqlite3.Connection | None = None) -> None:
        sql = "INSERT INTO role_grants(telegram_id, role, source, created_at) VALUES (?, ?, ?, ?)"
        params = (telegram_id, role.value, source, datetime.now(UTC).isoformat())
        if connection is not None:
            connection.execute(sql, params)
            return
        with self._database.transaction() as conn:
            conn.execute(sql, params)

    def resolve_roles(self, telegram_id: int, connection: sqlite3.Connection | None = None) -> set[Role]:
        sql = "SELECT role, source FROM role_grants WHERE telegram_id = ? ORDER BY id ASC"
        if connection is not None:
            rows = connection.execute(sql, (telegram_id,)).fetchall()
        else:
            with self._database.transaction() as conn:
                rows = conn.execute(sql, (telegram_id,)).fetchall()
        result: set[Role] = set()
        for row in rows:
            role = Role(row["role"])
            if row["source"] == "grant":
                result.add(role)
            elif row["source"] == "revoke":
                result.discard(role)
        return result

    def list_user_ids_with_role(self, role: Role, connection: sqlite3.Connection | None = None) -> list[int]:
        """Resolve all user ids that currently hold role according to append-only log."""

        if connection is not None:
            rows = connection.execute(
                "SELECT telegram_id, role, source FROM role_grants ORDER BY id ASC"
            ).fetchall()
        else:
            with self._database.transaction() as conn:
                rows = conn.execute("SELECT telegram_id, role, source FROM role_grants ORDER BY id ASC").fetchall()

        resolved: dict[int, set[Role]] = {}
        for row in rows:
            user_id = row["telegram_id"]
            row_role = Role(row["role"])
            resolved.setdefault(user_id, set())
            if row["source"] == "grant":
                resolved[user_id].add(row_role)
            elif row["source"] == "revoke":
                resolved[user_id].discard(row_role)
        return sorted(user_id for user_id, roles in resolved.items() if role in roles)
