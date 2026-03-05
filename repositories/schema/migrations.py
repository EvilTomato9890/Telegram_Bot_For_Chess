"""Simple SQL migration runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def apply_migrations(db_path: str | Path, migrations_dir: str | Path | None = None) -> None:
    migrations_root = Path(migrations_dir or Path(__file__).resolve().parents[1] / "migrations")
    migration_files = sorted(migrations_root.glob("*.sql"))

    if not migration_files:
        raise FileNotFoundError(f"No migration files found in {migrations_root}")

    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        applied = {
            row[0]
            for row in connection.execute("SELECT filename FROM schema_migrations").fetchall()
        }

        for migration_file in migration_files:
            if migration_file.name in applied:
                continue
            script = migration_file.read_text(encoding="utf-8")
            connection.executescript(script)
            connection.execute(
                "INSERT INTO schema_migrations(filename) VALUES (?)",
                (migration_file.name,),
            )

        connection.commit()
    finally:
        connection.close()
