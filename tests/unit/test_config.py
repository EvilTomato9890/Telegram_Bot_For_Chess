"""Configuration validation tests."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from domain.exceptions import DomainError
from infra.config import load_config


def _write_env(path: Path, *, token: str, db_url: str = "sqlite:///data/test_config.db", extra: tuple[str, ...] = ()) -> None:
    lines = [
        f"TOKEN={token}",
        f"DB_URL={db_url}",
        "ADMIN_IDS=1",
        "ARBITRS_IDS=2",
    ]
    lines.extend(extra)
    path.write_text("\n".join(lines), encoding="utf-8")


def _env_path(prefix: str) -> Path:
    root = Path("data")
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{prefix}_{uuid.uuid4().hex}.env"


def _clear_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("TOKEN", "DB_URL", "ADMIN_IDS", "ARBITRS_IDS", "STANDINGS_DEFAULT_TOP"):
        monkeypatch.delenv(key, raising=False)


def test_load_config_rejects_placeholder_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_config_env(monkeypatch)
    env_path = _env_path("cfg_placeholder")
    _write_env(env_path, token="1234567890:AAExampleTelegramBotToken1234567890")
    with pytest.raises(ValueError):
        load_config(env_path)


def test_load_config_accepts_realistic_token_format(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_config_env(monkeypatch)
    env_path = _env_path("cfg_valid")
    _write_env(env_path, token="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef012345")
    config = load_config(env_path)
    assert config.token.startswith("1234567890:")


def test_load_config_rejects_non_numeric_standings_default_top(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_config_env(monkeypatch)
    env_path = _env_path("cfg_top_invalid")
    _write_env(
        env_path,
        token="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef012345",
        extra=("STANDINGS_DEFAULT_TOP=abc",),
    )
    with pytest.raises(DomainError, match="STANDINGS_DEFAULT_TOP must be an integer"):
        load_config(env_path)


def test_load_config_uses_latest_dotenv_on_each_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_config_env(monkeypatch)
    first = _env_path("cfg_first")
    second = _env_path("cfg_second")
    _write_env(first, token="1111111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", db_url="sqlite:///data/first.db")
    _write_env(second, token="2222222222:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", db_url="sqlite:///data/second.db")

    config_first = load_config(first)
    config_second = load_config(second)

    assert config_first.token == "1111111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    assert config_second.token == "2222222222:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
    assert config_second.db_url == "sqlite:///data/second.db"
