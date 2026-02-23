"""Start menu keyboards."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def start_keyboard() -> ReplyKeyboardMarkup:
    """Main entry keyboard with required actions."""

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/register me 0 Имя Фамилия")],
            [KeyboardButton(text="/rules"), KeyboardButton(text="/standings 10")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

