"""Configuration validation tests."""

from __future__ import annotations

from pathlib import Path
import uuid

import pytest

from infra.config import load_config


def _write_env(path: Path, *, token: str) -> None:
    path.write_text(
        "\n".join(
            (
                f"TOKEN={token}",
                "DB_URL=sqlite:///data/test_config.db",
                "ADMIN_IDS=1",
                "ARBITRS_IDS=2",
            )
        ),
        encoding="utf-8",
    )


def _env_path(prefix: str) -> Path:
    root = Path("data")
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{prefix}_{uuid.uuid4().hex}.env"


def test_load_config_rejects_placeholder_token(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("TOKEN", "DB_URL", "ADMIN_IDS", "ARBITRS_IDS"):
        monkeypatch.delenv(key, raising=False)
    env_path = _env_path("cfg_placeholder")
    _write_env(env_path, token="1234567890:AAExampleTelegramBotToken1234567890")
    with pytest.raises(ValueError):
        load_config(env_path)


def test_load_config_accepts_realistic_token_format(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("TOKEN", "DB_URL", "ADMIN_IDS", "ARBITRS_IDS"):
        monkeypatch.delenv(key, raising=False)
    env_path = _env_path("cfg_valid")
    _write_env(env_path, token="1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef012345")
    config = load_config(env_path)
    assert config.token.startswith("1234567890:")
