"""SQLite database helpers.

The module provides small typed wrappers around sqlite3 to keep repositories
focused on SQL and mapping only.
"""

from __future__ import annotations

from domain.exceptions import DomainError

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


class Database:
    """A tiny SQLite connection factory with transaction helper."""

    def __init__(self, db_url: str) -> None:
        if not db_url.startswith("sqlite:///"):
            raise DomainError("Supported DB_URL format: sqlite:///path/to/file.db")
        self._db_path = Path(db_url.removeprefix("sqlite:///"))
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        """Filesystem path to sqlite database file."""

        return self._db_path

    def connect(self) -> sqlite3.Connection:
        """Create configured sqlite3 connection."""

        connection = sqlite3.connect(self._db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Connection context with commit/rollback semantics."""

        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()



