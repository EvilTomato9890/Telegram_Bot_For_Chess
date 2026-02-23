"""Player command shortcut keyboards."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def player_menu_keyboard() -> ReplyKeyboardMarkup:
    """Frequent player actions."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/my_next"), KeyboardButton(text="/my_score")],
            [KeyboardButton(text="/schedule"), KeyboardButton(text="/standings 10")],
            [KeyboardButton(text="/report"), KeyboardButton(text="/create_ticket arbitr Нужен арбитр")],
        ],
        resize_keyboard=True,
    )

