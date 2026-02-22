"""Centralized logger configuration.

A single configuration function is used so every module logs with the same
format, level, and sinks.
"""

from __future__ import annotations

import logging
import sys

from loguru import logger


def _to_stdlib_level(level: str) -> int | str:
    """Convert configured level to value accepted by stdlib logging."""
    normalized = level.upper()
    if normalized == "TRACE":
        logging.addLevelName(5, "TRACE")
        return 5
    return normalized


class _InterceptHandler(logging.Handler):
    """Forward stdlib logging records to Loguru sink."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: int | str = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logger(level: str) -> None:
    """Configure global Loguru logger for stdout with compact JSON-like context."""
    normalized_level = level.upper()
    stdlib_level = _to_stdlib_level(normalized_level)

    logging.root.handlers = [_InterceptHandler()]
    logging.root.setLevel(stdlib_level)
    for logger_name in ("aiogram", "sqlalchemy", "alembic", "asyncio"):
        std_logger = logging.getLogger(logger_name)
        std_logger.handlers = [_InterceptHandler()]
        std_logger.setLevel(stdlib_level)
        std_logger.propagate = False

    logger.remove()
    logger.add(
        sys.stdout,
        level=normalized_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | {message}",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
