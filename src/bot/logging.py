"""Centralized logger configuration.

A single configuration function is used so every module logs with the same
format, level, and sinks.
"""

from __future__ import annotations

import sys
import logging

from loguru import logger


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
    logging.root.handlers = [_InterceptHandler()]
    logging.root.setLevel(level.upper())
    for logger_name in ("aiogram", "sqlalchemy", "alembic", "asyncio"):
        std_logger = logging.getLogger(logger_name)
        std_logger.handlers = [_InterceptHandler()]
        std_logger.setLevel(level.upper())
        std_logger.propagate = False

    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | {message}",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )
