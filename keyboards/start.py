"""Start menu keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def start_keyboard() -> InlineKeyboardMarkup:
    """Entry keyboard with exactly two actions."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Регистрация", callback_data="start:register"),
                InlineKeyboardButton(text="🏆 Мой турнир", callback_data="start:my_tournament"),
            ]
        ]
    )

