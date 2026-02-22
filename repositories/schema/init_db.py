"""Command-line database initialization helper."""

from __future__ import annotations

import argparse
from pathlib import Path

from .migrations import apply_migrations


def init_db(db_url: str) -> Path:
    if not db_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// URLs are supported by the bootstrap initializer")

    db_path = Path(db_url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    apply_migrations(db_path)
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
