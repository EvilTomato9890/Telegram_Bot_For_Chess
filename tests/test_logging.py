from pathlib import Path

from infra.logging import setup_logging


def test_audit_log_writes_required_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.log"

    audit_logger = setup_logging(level="INFO", audit_log_path=str(log_path))
    audit_logger.log_event(
        actor="admin:1",
        command="/finish",
        entity="tournament:42",
        action="close",
        result="ok",
    )

    content = log_path.read_text(encoding="utf-8")

    assert "actor=admin:1" in content
    assert "command=/finish" in content
    assert "entity=tournament:42" in content
    assert "action=close" in content
    assert "result=ok" in content
