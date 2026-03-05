"""Application settings loader."""

from __future__ import annotations

import os
import re
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


def _load_dotenv(dotenv_path: Path) -> None:
    """Load dotenv pairs if process env does not already define a key."""

    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _required(name: str) -> str:
    value = os.getenv(name)
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
    value = int(raw)
    if value <= 0:
        raise DomainError("STANDINGS_DEFAULT_TOP must be positive")
    return value


def load_config(dotenv_path: str | Path = ".env") -> AppConfig:
    """Load and validate app config."""

    _load_dotenv(Path(dotenv_path))
    return AppConfig(
        token=_validate_token(_required("TOKEN")),
        db_url=_required("DB_URL"),
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS"), field_name="ADMIN_IDS"),
        arbitrs_ids=_parse_ids(os.getenv("ARBITRS_IDS"), field_name="ARBITRS_IDS"),
        timezone=os.getenv("TIMEZONE", "UTC"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        audit_log_path=os.getenv("AUDIT_LOG_PATH", "logs/audit.log"),
        default_rules=os.getenv("DEFAULT_RULES", "Правила турнира пока не заданы."),
        standings_default_top=_parse_positive_int(os.getenv("STANDINGS_DEFAULT_TOP"), default=10),
    )


__all__ = ["AppConfig", "load_config"]



