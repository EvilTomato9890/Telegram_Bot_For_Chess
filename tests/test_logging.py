import logging

from loguru import logger

from bot.logging import configure_logger


def test_configure_logger_forwards_stdlib_logging() -> None:
    configure_logger("TRACE")

    messages: list[str] = []
    sink_id = logger.add(messages.append, level="TRACE", format="{level}:{message}")
    try:
        logging.getLogger("aiogram.dispatcher").debug("debug from stdlib")
    finally:
        logger.remove(sink_id)

    assert any("DEBUG:debug from stdlib" in message for message in messages)


def test_configure_logger_captures_python_warnings() -> None:
    configure_logger("TRACE")

    messages: list[str] = []
    sink_id = logger.add(messages.append, level="WARNING", format="{message}")
    try:
        logging.getLogger("py.warnings").warning("warning from stdlib")
    finally:
        logger.remove(sink_id)

    assert any("warning from stdlib" in message for message in messages)
