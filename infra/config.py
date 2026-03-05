"""Application settings loader."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from domain.exceptions import DomainError


@dataclass(slots=True)
class AppConfig:
    """Runtime config read from environment and `.env` file."""

    token: str
    db_url: str
    admin_ids: list[int]
    arbitrs_ids: list[int]
    timezone: str
    log_level: str
    audit_log_path: str
    default_rules: str
    standings_default_top: int


def _read_dotenv(dotenv_path: Path) -> dict[str, str]:
    """Read dotenv file into plain mapping without mutating process env."""

    values: dict[str, str] = {}
    if not dotenv_path.exists():
        return values
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_value(name: str, dotenv_values: Mapping[str, str]) -> str | None:
    value = os.getenv(name)
    if value is not None:
        return value
    return dotenv_values.get(name)


def _required(name: str, *, dotenv_values: Mapping[str, str]) -> str:
    value = _env_value(name, dotenv_values)
    if value is None or value.strip() == "":
        raise DomainError(f"Missing required environment variable: {name}")
    return value


_TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")
_TOKEN_PLACEHOLDER_MARKERS = (
    "exampletelegrambottoken",
    "replace_with_real_bot_token",
    "your_real_bot_token",
    "your_bot_token_here",
)


def _validate_token(raw_token: str) -> str:
    """Validate bot token format and common placeholder values."""

    token = raw_token.strip()
    lower_token = token.lower()
    if any(marker in lower_token for marker in _TOKEN_PLACEHOLDER_MARKERS):
        raise DomainError(
            "TOKEN похож на шаблонный. Укажите реальный токен от BotFather в .env."
        )
    if not _TOKEN_PATTERN.match(token):
        raise DomainError(
            "Некорректный формат TOKEN. Ожидается строка вида '<digits>:<secret>'."
        )
    return token


def _parse_ids(raw: str | None, *, field_name: str) -> list[int]:
    if raw is None or raw.strip() == "":
        return []
    items = [part.strip() for part in raw.split(",") if part.strip()]
    try:
        return [int(item) for item in items]
    except ValueError as exc:
        raise DomainError(f"{field_name} must contain comma-separated integers") from exc


def _parse_positive_int(raw: str | None, *, default: int) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise DomainError("STANDINGS_DEFAULT_TOP must be an integer") from exc
    if value <= 0:
        raise DomainError("STANDINGS_DEFAULT_TOP must be positive")
    return value


def load_config(dotenv_path: str | Path = ".env") -> AppConfig:
    """Load and validate app config."""

    dotenv_values = _read_dotenv(Path(dotenv_path))
    timezone = _env_value("TIMEZONE", dotenv_values)
    log_level = _env_value("LOG_LEVEL", dotenv_values)
    audit_log_path = _env_value("AUDIT_LOG_PATH", dotenv_values)
    default_rules = _env_value("DEFAULT_RULES", dotenv_values)
    return AppConfig(
        token=_validate_token(_required("TOKEN", dotenv_values=dotenv_values)),
        db_url=_required("DB_URL", dotenv_values=dotenv_values),
        admin_ids=_parse_ids(_env_value("ADMIN_IDS", dotenv_values), field_name="ADMIN_IDS"),
        arbitrs_ids=_parse_ids(_env_value("ARBITRS_IDS", dotenv_values), field_name="ARBITRS_IDS"),
        timezone=timezone if timezone is not None else "UTC",
        log_level=log_level if log_level is not None else "INFO",
        audit_log_path=audit_log_path if audit_log_path is not None else "logs/audit.log",
        default_rules=default_rules if default_rules is not None else "Правила турнира пока не заданы.",
        standings_default_top=_parse_positive_int(_env_value("STANDINGS_DEFAULT_TOP", dotenv_values), default=10),
    )


__all__ = ["AppConfig", "load_config"]

