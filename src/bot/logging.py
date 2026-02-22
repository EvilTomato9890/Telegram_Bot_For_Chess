"""Centralized logger configuration.

A single configuration function is used so every module logs with the same
format, level, and sinks.
"""

from __future__ import annotations

import sys

from loguru import logger


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
