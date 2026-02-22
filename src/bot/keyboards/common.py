"""Inline keyboard builders used across handlers."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Return the main bot menu for players and organizers."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Текущий турнир", callback_data="tournament:current")],
            [InlineKeyboardButton(text="📝 Регистрация", callback_data="player:register")],
        ]
    )
