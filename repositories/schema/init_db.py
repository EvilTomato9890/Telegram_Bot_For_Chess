"""Command-line database initialization helper."""

from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

from .migrations import apply_migrations


_REQUIRED_TABLES = {
    "tournaments",
    "players",
    "rounds",
    "tables",
    "games",
    "game_reports",
    "tickets",
    "role_grants",
    "undo_snapshots",
}


def _table_names(db_path: Path) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {row[0] for row in rows}
    finally:
        connection.close()


def _rebuild_schema(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        rows = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
        for (name,) in rows:
            connection.execute(f"DROP TABLE IF EXISTS {name}")
        connection.commit()
    finally:
        connection.close()
    apply_migrations(db_path)


def init_db(db_url: str) -> Path:
    if not db_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// URLs are supported by the bootstrap initializer")

    db_path = Path(db_url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        apply_migrations(db_path)
    except sqlite3.OperationalError:
        # Backward-compatible recovery for incompatible historical schemas.
        _rebuild_schema(db_path)
    names = _table_names(db_path)
    if not _REQUIRED_TABLES.issubset(names):
        _rebuild_schema(db_path)
    return db_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize application database")
    parser.add_argument("db_url", help="Database URL, e.g. sqlite:///data/tournament.db")
    args = parser.parse_args()

    db_path = init_db(args.db_url)
    print(f"Database initialized at: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
