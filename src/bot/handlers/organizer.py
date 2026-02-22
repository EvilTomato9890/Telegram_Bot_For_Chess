"""Handlers for organizer-only commands."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.acl import AccessControlService

router = Router(name="organizer")


@router.message(Command("organizer"))
async def organizer_help(message: Message, acl: AccessControlService) -> None:
    """Show organizer panel command hints if the user has required rights."""
    user = message.from_user
    if user is None or not acl.is_organizer(user.id):
        await message.answer("У вас нет прав организатора для этой команды.")
        return

    await message.answer("Команды организатора: /organizer, /create_tournament, /pair_round")
