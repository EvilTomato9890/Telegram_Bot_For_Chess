import logging

from bot.logging import configure_logger


def test_configure_logger_accepts_trace_for_stdlib_logging() -> None:
    configure_logger("TRACE")

    assert logging.getLevelName(5) == "TRACE"
    assert logging.getLogger().level == 5
    assert logging.getLogger("aiogram").level == 5


def test_configure_logger_accepts_loguru_success_level_for_stdlib_logging() -> None:
    configure_logger("SUCCESS")

    assert logging.getLevelName(25) == "SUCCESS"
    assert logging.getLogger().level == 25


def test_configure_logger_falls_back_to_info_for_unknown_level() -> None:
    configure_logger("NON_EXISTENT_LEVEL")

    assert logging.getLogger().level == logging.INFO
