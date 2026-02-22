"""Centralized logger configuration.

A single configuration function is used so every module logs with the same
format, level, and sinks.
"""

from __future__ import annotations

import logging
import sys

from loguru import logger


class _InterceptHandler(logging.Handler):
    """Forward standard-library logging records to Loguru.

    This allows logs from aiogram/sqlalchemy/asyncio and any other library that
    uses `logging` to appear in the same sink and respect the configured level.
    """

    def emit(self, record: logging.LogRecord) -> None:
        level = record.levelname
        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logger(level: str) -> None:
    """Configure global Loguru logger for stdout with compact JSON-like context."""
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

    # Capture logs from stdlib logging users (aiogram, sqlalchemy, asyncio, etc.).
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    logging.captureWarnings(True)

    # Ensure noisy but valuable framework logs are available when TRACE/DEBUG is enabled.
    for logger_name in ("aiogram", "sqlalchemy", "asyncio", "alembic"):
        logging.getLogger(logger_name).setLevel(logging.NOTSET)
