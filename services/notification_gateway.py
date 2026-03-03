"""Gateway for outbound Telegram notifications."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import logging

from aiogram import Bot

from .notification_service import NotificationService


class NotificationGateway:
    """Unified gateway for sending notifications through Telegram Bot API."""

    def __init__(self, sink: NotificationService | None = None) -> None:
        self._sink = sink
        self._logger = logging.getLogger(__name__)

    async def send_to_user(self, bot: Bot | None, telegram_id: int, text: str) -> bool:
        """Send one message to one user.

        Returns True on successful delivery, False otherwise.
        """

        if self._sink is not None:
            self._sink.notify(f"[TO:{telegram_id}] {text}")
        if bot is None:
            return False
        try:
            await bot.send_message(telegram_id, text)
            return True
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Failed to deliver message to %s: %s", telegram_id, exc)
            return False

    async def broadcast(
        self,
        bot: Bot | None,
        telegram_ids: Iterable[int],
        text_builder: Callable[[int], str],
    ) -> tuple[int, int]:
        """Broadcast messages and return (attempted, delivered)."""

        attempted = 0
        delivered = 0
        for telegram_id in telegram_ids:
            attempted += 1
            text = text_builder(telegram_id)
            if await self.send_to_user(bot, telegram_id, text):
                delivered += 1
        return (attempted, delivered)
