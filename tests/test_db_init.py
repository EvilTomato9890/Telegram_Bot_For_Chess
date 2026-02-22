import sqlite3
from pathlib import Path

from repositories.schema import init_db


def test_init_db_creates_all_required_tables(tmp_path: Path) -> None:
    db_path = init_db(f"sqlite:///{tmp_path / 'app.db'}")
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    finally:
        connection.close()

    tables = {row[0] for row in rows}
    assert {
        "schema_migrations",
        "tournaments",
        "players",
        "rounds",
        "tables",
        "seats",
        "games",
        "tickets",
    }.issubset(tables)
