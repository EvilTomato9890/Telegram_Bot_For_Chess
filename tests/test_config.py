from pathlib import Path

from pytest import MonkeyPatch

from infra.config import load_config


ENV_KEYS = [
    "TOKEN",
    "ADMIN_IDS",
    "ARBITRS_IDS",
    "TIMEZONE",
    "DB_URL",
    "LOG_LEVEL",
    "AUDIT_LOG_PATH",
]


def test_load_config_from_dotenv(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "\n".join(
            [
                "TOKEN=test-token",
                "ADMIN_IDS=1,2",
                "ARBITRS_IDS=5,8",
                "TIMEZONE=Europe/Moscow",
                "DB_URL=sqlite:///db.sqlite3",
                "LOG_LEVEL=DEBUG",
                "AUDIT_LOG_PATH=logs/custom_audit.log",
            ]
        ),
        encoding="utf-8",
    )

    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config = load_config(dotenv)

    assert config.token == "test-token"
    assert config.admin_ids == [1, 2]
    assert config.arbitrs_ids == [5, 8]
    assert config.timezone == "Europe/Moscow"
    assert config.db_url == "sqlite:///db.sqlite3"
    assert config.log_level == "DEBUG"
    assert config.audit_log_path == "logs/custom_audit.log"


def test_load_config_is_deterministic_across_different_dotenv_paths(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    first_env = tmp_path / "first.env"
    second_env = tmp_path / "second.env"
    first_env.write_text("TOKEN=first\nDB_URL=sqlite:///first.db\n", encoding="utf-8")
    second_env.write_text("TOKEN=second\nDB_URL=sqlite:///second.db\n", encoding="utf-8")

    first = load_config(first_env)
    second = load_config(second_env)

    assert first.token == "first"
    assert second.token == "second"
    assert first.db_url == "sqlite:///first.db"
    assert second.db_url == "sqlite:///second.db"


def test_os_environment_has_priority_over_dotenv(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("TOKEN=file-token\nDB_URL=file-db\n", encoding="utf-8")

    monkeypatch.setenv("TOKEN", "env-token")
    monkeypatch.setenv("DB_URL", "env-db")

    config = load_config(dotenv)

    assert config.token == "env-token"
    assert config.db_url == "env-db"
