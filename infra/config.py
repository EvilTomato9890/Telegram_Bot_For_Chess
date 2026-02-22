"""Application configuration loading utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(slots=True)
class AppConfig:
    """Typed runtime settings loaded from environment."""

    token: str
    admin_ids: list[int]
    arbitrs_ids: list[int]
    timezone: str
    db_url: str
    log_level: str = "INFO"
    audit_log_path: str = "logs/audit.log"


def _load_dotenv(dotenv_path: Path) -> None:
    """Load key/value pairs from .env into process environment if unset."""

    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _parse_int_list(raw_value: str | None, *, field_name: str) -> list[int]:
    if raw_value is None or raw_value.strip() == "":
        return []

    parsed: list[int] = []
    for part in raw_value.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            parsed.append(int(item))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a comma-separated list of integers") from exc
    return parsed


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config(dotenv_path: str | Path = ".env") -> AppConfig:
    """Load application config from `.env` and environment variables."""

    _load_dotenv(Path(dotenv_path))

    return AppConfig(
        token=_get_required("TOKEN"),
        admin_ids=_parse_int_list(os.getenv("ADMIN_IDS"), field_name="ADMIN_IDS"),
        arbitrs_ids=_parse_int_list(os.getenv("ARBITRS_IDS"), field_name="ARBITRS_IDS"),
        timezone=os.getenv("TIMEZONE", "UTC"),
        db_url=_get_required("DB_URL"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        audit_log_path=os.getenv("AUDIT_LOG_PATH", "logs/audit.log"),
    )


__all__ = ["AppConfig", "load_config"]
