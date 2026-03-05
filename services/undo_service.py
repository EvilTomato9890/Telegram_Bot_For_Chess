"""Admin undo support."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

from domain.dto import UndoResult
from domain.exceptions import DomainError
from domain.models import UndoSnapshot
from infra.db import Database
from infra.logging import AuditLogger
from repositories import UndoRepository

from .acl_service import AccessControlService


class UndoService:
    """Store and restore full tournament snapshots."""

    SNAPSHOT_TABLES: tuple[str, ...] = (
        "tournaments",
        "players",
        "rounds",
        "tables",
        "games",
        "game_reports",
        "tickets",
        "role_grants",
    )
    # Delete children first to satisfy FK constraints.
    RESTORE_DELETE_ORDER: tuple[str, ...] = (
        "game_reports",
        "tickets",
        "games",
        "rounds",
        "players",
        "tables",
        "role_grants",
        "tournaments",
    )
    # Insert parents first to satisfy FK constraints.
    RESTORE_INSERT_ORDER: tuple[str, ...] = (
        "tournaments",
        "players",
        "rounds",
        "tables",
        "games",
        "game_reports",
        "tickets",
        "role_grants",
    )

    def __init__(
        self,
        database: Database,
        undo_repo: UndoRepository,
        acl_service: AccessControlService,
        audit_logger: AuditLogger,
    ) -> None:
        self._database = database
        self._undo_repo = undo_repo
        self._acl_service = acl_service
        self._audit_logger = audit_logger

    def snapshot(self, actor_id: int, action_name: str) -> UndoSnapshot:
        """Capture one full-state snapshot before mutation."""

        payload: dict[str, list[dict[str, object]]] = {}
        with self._database.transaction() as conn:
            for table in self.SNAPSHOT_TABLES:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                payload[table] = [{key: row[key] for key in row.keys()} for row in rows]
            snapshot = self._undo_repo.add(
                UndoSnapshot(
                    id=None,
                    actor_telegram_id=actor_id,
                    action_name=action_name,
                    snapshot_json=json.dumps(payload, ensure_ascii=False),
                    created_at=datetime.now(UTC),
                ),
                connection=conn,
            )
            return snapshot

    def discard_snapshot(self, snapshot_id: int) -> None:
        """Delete snapshot when command failed before any domain mutation."""

        self._undo_repo.delete_by_id(snapshot_id)

    def undo_last_admin_action(self, actor_id: int) -> UndoResult:
        """Restore most recent unrestored snapshot for current admin."""

        snapshot = self._undo_repo.get_last_unrestored(actor_telegram_id=actor_id)
        if snapshot is None or snapshot.id is None:
            raise DomainError("Нет действий для отката.")

        payload = json.loads(snapshot.snapshot_json)
        payload_map = cast(dict[str, Any], payload)
        with self._database.transaction() as conn:
            for table in self.RESTORE_DELETE_ORDER:
                conn.execute(f"DELETE FROM {table}")
            for table in self.RESTORE_INSERT_ORDER:
                rows_raw = payload_map.get(table, [])
                if not isinstance(rows_raw, list):
                    continue
                rows: list[dict[str, object]] = [row for row in rows_raw if isinstance(row, dict)]
                if not rows:
                    continue
                columns = list(rows[0].keys())
                placeholders = ", ".join("?" for _ in columns)
                column_sql = ", ".join(columns)
                for row in rows:
                    conn.execute(
                        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
                        tuple(row[column] for column in columns),
                    )
            self._undo_repo.mark_restored(snapshot.id, connection=conn)

        restored_at = datetime.now(UTC)
        self._audit_logger.log_event(
            actor_id=actor_id,
            roles=[role.value for role in self._acl_service.resolve_roles(actor_id)],
            command="/undo_last_action",
            entity=f"undo:{snapshot.id}",
            before={"action": snapshot.action_name},
            after={"restored": True, "undone_action": snapshot.action_name},
            result="ok",
            reason=None,
        )
        return UndoResult(
            snapshot_id=snapshot.id,
            undone_action=snapshot.action_name,
            restored_at=restored_at,
        )

