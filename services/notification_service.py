"""Notification abstraction.

The service stores generated notifications in memory for tests and potential
future adapters; routers may flush and deliver these messages via Telegram.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NotificationService:
    """Collect outbound messages in outbox."""

    _outbox: list[str] = field(default_factory=list)

    def notify(self, message: str) -> None:
        """Push one notification to outbox."""

        self._outbox.append(message)

    def flush(self) -> list[str]:
        """Return and clear notifications."""

        messages = [*self._outbox]
        self._outbox.clear()
        return messages

