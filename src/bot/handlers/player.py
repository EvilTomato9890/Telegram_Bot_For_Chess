"""Handlers for player-facing commands."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.common import main_menu_keyboard

router = Router(name="player")


@router.message(CommandStart())
async def start_player(message: Message) -> None:
    """Greet regular users and show available player actions."""
    await message.answer(
        "Добро пожаловать в турнирного бота! Выберите действие в меню ниже.",
        reply_markup=main_menu_keyboard(),
    )
