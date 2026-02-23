"""Fallback router for unknown slash commands."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message


def build_fallback_router() -> Router:
    """Create router handling unknown commands."""

    router = Router(name="fallback")

    @router.message(F.text.startswith("/"))
    async def unknown_command_handler(message: Message) -> None:
        await message.answer("Команда не распознана. Используйте /help")

    return router

