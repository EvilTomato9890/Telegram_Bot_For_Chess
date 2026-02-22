"""Database infrastructure package."""

from bot.db.migrations import initialize_database

__all__ = ["initialize_database"]
