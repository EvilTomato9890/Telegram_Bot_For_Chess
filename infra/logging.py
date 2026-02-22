"""Logging configuration for application and audit events."""

from __future__ import annotations

import logging
from pathlib import Path


class AuditFormatter(logging.Formatter):
    """Structured formatter for audit records."""

    def format(self, record: logging.LogRecord) -> str:
        actor = getattr(record, "actor", "-")
        command = getattr(record, "command", "-")
        entity = getattr(record, "entity", "-")
        action = getattr(record, "action", "-")
        result = getattr(record, "result", "-")
        return (
            f"{self.formatTime(record)} | actor={actor} | command={command} "
            f"| entity={entity} | action={action} | result={result}"
        )


class AuditLogger:
    """Simple helper to write audit events with required fields."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def log_event(self, *, actor: str, command: str, entity: str, action: str, result: str) -> None:
        self._logger.info(
            "audit_event",
            extra={
                "actor": actor,
                "command": command,
                "entity": entity,
                "action": action,
                "result": result,
            },
        )


def setup_logging(level: str = "INFO", audit_log_path: str = "logs/audit.log") -> AuditLogger:
    """Configure console and audit loggers."""

    console_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=console_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    audit_path = Path(audit_log_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False

    for handler in list(audit_logger.handlers):
        audit_logger.removeHandler(handler)
        handler.close()

    file_handler = logging.FileHandler(audit_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(AuditFormatter())
    audit_logger.addHandler(file_handler)

    return AuditLogger(audit_logger)


__all__ = ["AuditLogger", "setup_logging"]
