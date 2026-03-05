"""Command-line database initialization helper."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from domain.exceptions import DomainError

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


def _incompatible_schema_error(db_path: Path) -> RuntimeError:
    message = (
        "Incompatible existing schema detected for "
        f"{db_path}. Run `python -m repositories.schema.init_db "
        f"sqlite:///{db_path.as_posix()} --rebuild` to recreate the database."
    )
    return RuntimeError(message)


def init_db(db_url: str, *, rebuild_on_incompatible: bool = False) -> Path:
    if not db_url.startswith("sqlite:///"):
        raise DomainError("Only sqlite:/// URLs are supported by the bootstrap initializer")

    db_path = Path(db_url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        apply_migrations(db_path)
    except sqlite3.OperationalError as exc:
        if rebuild_on_incompatible:
            _rebuild_schema(db_path)
        else:
            raise _incompatible_schema_error(db_path) from exc
    names = _table_names(db_path)
    if not _REQUIRED_TABLES.issubset(names):
        if rebuild_on_incompatible:
            _rebuild_schema(db_path)
        else:
            raise _incompatible_schema_error(db_path)
    return db_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize application database")
    parser.add_argument("db_url", help="Database URL, e.g. sqlite:///data/tournament.db")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop existing schema and recreate it when incompatible",
    )
    args = parser.parse_args()

    db_path = init_db(args.db_url, rebuild_on_incompatible=args.rebuild)
    print(f"Database initialized at: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

