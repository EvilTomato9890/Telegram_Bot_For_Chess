from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from infra.config import load_config


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

    for key in [
        "TOKEN",
        "ADMIN_IDS",
        "ARBITRS_IDS",
        "TIMEZONE",
        "DB_URL",
        "LOG_LEVEL",
        "AUDIT_LOG_PATH",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = load_config(dotenv)

    assert config.token == "test-token"
    assert config.admin_ids == [1, 2]
    assert config.arbitrs_ids == [5, 8]
    assert config.timezone == "Europe/Moscow"
    assert config.db_url == "sqlite:///db.sqlite3"
    assert config.log_level == "DEBUG"
    assert config.audit_log_path == "logs/custom_audit.log"
