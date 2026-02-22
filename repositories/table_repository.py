"""Table repository interfaces and in-memory implementation."""

from __future__ import annotations

from dataclasses import replace

from domain.models import Table


class TableRepository:
    """Storage adapter for tables."""

    def __init__(self) -> None:
        self._tables: dict[int, Table] = {}
        self._next_id = 1

    def add(self, table: Table) -> Table:
        table_id = self._next_id if table.id is None else table.id
        self._next_id = max(self._next_id, table_id + 1)
        stored = replace(table, id=table_id)
        self._tables[table_id] = stored
        return stored

    def list_by_round(self, round_id: int) -> list[Table]:
        return [t for t in self._tables.values() if t.round_id == round_id]


__all__ = ["TableRepository"]
