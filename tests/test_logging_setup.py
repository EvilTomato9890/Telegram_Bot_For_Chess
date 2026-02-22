import logging

from bot.logging import configure_logger


def test_configure_logger_accepts_trace_for_stdlib_logging() -> None:
    configure_logger("TRACE")

    assert logging.getLevelName(5) == "TRACE"
    assert logging.getLogger().level == 5
    assert logging.getLogger("aiogram").level == 5
