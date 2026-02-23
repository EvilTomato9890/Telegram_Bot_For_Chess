from __future__ import annotations

from handlers.common.response_formatter import KeyboardMessage, ResponseFormatter


def build_start_keyboard_message() -> KeyboardMessage:
    """Build start message with quick actions for player onboarding."""
    return KeyboardMessage(
        text=ResponseFormatter.START_KEYBOARD_TEXT,
        buttons=("регистрация", "текущая информация"),
    )
