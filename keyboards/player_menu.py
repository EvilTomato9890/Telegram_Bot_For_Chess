"""Player command shortcut keyboards."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def player_menu_keyboard() -> ReplyKeyboardMarkup:
    """Frequent player actions in compact styled layout."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/my_next 🗓"), KeyboardButton(text="/my_score 📊")],
            [KeyboardButton(text="/standings 10 🏁"), KeyboardButton(text="/schedule 📅")],
            [KeyboardButton(text="/report 📝"), KeyboardButton(text="/get_game_id 🆔")],
            [KeyboardButton(text="/rules 📜"), KeyboardButton(text="/help ❓")],
            [KeyboardButton(text="/create_ticket arbitr Нужен арбитр")],
        ],
        resize_keyboard=True,
    )


