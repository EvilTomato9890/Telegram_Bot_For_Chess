import sqlite3
from pathlib import Path

import pytest

from repositories.schema.init_db import init_db
from tests.utils import build_db_url


def test_init_db_does_not_rebuild_incompatible_schema_by_default() -> None:
    db_url = build_db_url("init_safety")
    db_path = Path(db_url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Simulate old/incompatible state: migration 001 marked as applied but
    # required current tables are absent.
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute("INSERT INTO schema_migrations(filename) VALUES ('001_initial_schema.sql')")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(RuntimeError, match="Incompatible existing schema detected"):
        init_db(db_url)


def test_init_db_rebuild_flag_allows_recovery() -> None:
    db_url = build_db_url("init_rebuild")
    db_path = Path(db_url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute("INSERT INTO schema_migrations(filename) VALUES ('001_initial_schema.sql')")
        connection.commit()
    finally:
        connection.close()

    init_db(db_url, rebuild_on_incompatible=True)

    connection = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        connection.close()
    assert "role_grants" in tables
