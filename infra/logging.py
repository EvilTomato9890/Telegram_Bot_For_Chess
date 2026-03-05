"""Logging setup with dedicated structured audit sink."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AuditFormatter(logging.Formatter):
    """Serialize audit log record into deterministic JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record),
            "actor_id": getattr(record, "actor_id", None),
            "roles": getattr(record, "roles", []),
            "command": getattr(record, "command", ""),
            "entity": getattr(record, "entity", ""),
            "before": getattr(record, "before", None),
            "after": getattr(record, "after", None),
            "result": getattr(record, "result", ""),
            "reason": getattr(record, "reason", None),
        }
        return json.dumps(payload, ensure_ascii=False)


@dataclass(slots=True)
class AuditLogger:
    """Structured audit event writer."""

    logger: logging.Logger

    def log_event(
        self,
        *,
        actor_id: int | str,
        roles: list[str] | tuple[str, ...],
        command: str,
        entity: str,
        before: Any,
        after: Any,
        result: str,
        reason: str | None = None,
    ) -> None:
        """Write one audit event."""

        self.logger.info(
            "audit_event",
            extra={
                "actor_id": actor_id,
                "roles": list(roles),
                "command": command,
                "entity": entity,
                "before": before,
                "after": after,
                "result": result,
                "reason": reason,
            },
        )


def setup_logging(level: str = "INFO", audit_log_path: str = "logs/audit.log") -> AuditLogger:
    """Initialize console logger and dedicated audit logger."""

    console_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(console_level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s | %(message)s",
            defaults={"request_id": "-"},
        )
    )
    root_logger.addHandler(console_handler)

    audit_path = Path(audit_log_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_sink = logging.getLogger("audit")
    audit_sink.handlers.clear()
    audit_sink.setLevel(logging.INFO)
    audit_sink.propagate = False

    file_handler = logging.FileHandler(audit_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(AuditFormatter())
    audit_sink.addHandler(file_handler)

    return AuditLogger(logger=audit_sink)


__all__ = ["AuditLogger", "setup_logging"]
