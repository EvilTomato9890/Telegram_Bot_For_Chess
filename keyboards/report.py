"""Inline keyboards for result reporting."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def report_keyboard() -> InlineKeyboardMarkup:
    """Buttons for White/Black/Draw report flow."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚪ White", callback_data="report:white"),
                InlineKeyboardButton(text="⚫ Black", callback_data="report:black"),
                InlineKeyboardButton(text="🤝 Draw", callback_data="report:draw"),
            ]
        ]
    )


