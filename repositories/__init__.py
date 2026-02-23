"""Repository exports."""

from .schema import apply_migrations
from .sqlite import (
    GameReportRepository,
    GameRepository,
    PlayerRepository,
    RoleGrantRepository,
    RoundRepository,
    TableRepository,
    TicketRepository,
    TournamentRepository,
    UndoRepository,
)


def init_db(db_url: str):
    """Lazy import wrapper to avoid module re-import warnings."""

    from .schema.init_db import init_db as _init_db

    return _init_db(db_url)

__all__ = [
    "apply_migrations",
    "init_db",
    "TournamentRepository",
    "PlayerRepository",
    "RoundRepository",
    "GameRepository",
    "TableRepository",
    "TicketRepository",
    "GameReportRepository",
    "UndoRepository",
    "RoleGrantRepository",
]
