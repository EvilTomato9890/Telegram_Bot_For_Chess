"""Application configuration loading utilities."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


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


def _read_dotenv(dotenv_path: Path) -> dict[str, str]:
    """Read key/value pairs from a .env file without mutating process env."""

    if not dotenv_path.exists():
        return {}

    result: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


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


def _get_required(source: dict[str, str], name: str) -> str:
    value = source.get(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_config(dotenv_path: str | Path = ".env") -> AppConfig:
    """Load application config from `.env` and environment variables."""

    dotenv_values = _read_dotenv(Path(dotenv_path))
    source: dict[str, str] = {**dotenv_values, **dict(os.environ)}

    return AppConfig(
        token=_get_required(source, "TOKEN"),
        admin_ids=_parse_int_list(source.get("ADMIN_IDS"), field_name="ADMIN_IDS"),
        arbitrs_ids=_parse_int_list(source.get("ARBITRS_IDS"), field_name="ARBITRS_IDS"),
        timezone=source.get("TIMEZONE", "UTC"),
        db_url=_get_required(source, "DB_URL"),
        log_level=source.get("LOG_LEVEL", "INFO"),
        audit_log_path=source.get("AUDIT_LOG_PATH", "logs/audit.log"),
    )


__all__ = ["AppConfig", "load_config"]
