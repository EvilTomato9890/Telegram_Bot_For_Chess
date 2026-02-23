"""Inline keyboards for ticket creation."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def ticket_type_keyboard() -> InlineKeyboardMarkup:
    """Quick choice between arbitrator and organizer ticket type."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚖️ Арбитр", callback_data="ticket:arbitr"),
                InlineKeyboardButton(text="🛠 Админ", callback_data="ticket:organizer"),
            ]
        ]
    )

