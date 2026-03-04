import sqlite3

from repositories import init_db
from tests.utils import build_db_url


def test_migrations_create_required_tables() -> None:
    db_url = build_db_url("migrations")
    db_path = init_db(db_url)
    connection = sqlite3.connect(db_path)
    try:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        connection.close()
    assert {
        "tournaments",
        "players",
        "rounds",
        "tables",
        "games",
        "game_reports",
        "tickets",
        "role_grants",
        "undo_snapshots",
    }.issubset(names)


def test_migrations_are_idempotent() -> None:
    db_url = build_db_url("migrations_idempotent")
    path = init_db(db_url)
    init_db(db_url)
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("SELECT filename FROM schema_migrations ORDER BY filename").fetchall()
    finally:
        connection.close()
    assert rows == [("001_initial_schema.sql",), ("002_reports_undo_indexes.sql",)]

