"""Access-control service for role checks."""

from __future__ import annotations


class AccessControlService:
    """Encapsulates organizer permission checks."""

    def __init__(self, admin_ids: set[int]) -> None:
        self._admin_ids = admin_ids

    def is_organizer(self, user_id: int) -> bool:
        """Return whether a user has organizer rights."""
        return user_id in self._admin_ids
