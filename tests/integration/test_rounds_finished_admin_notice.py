import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from bot.context import RouterContext
from bot.routers.organizer import build_organizer_router
from domain.models import Round, RoundStatus, TournamentStatus
from infra.config import AppConfig
from infra.logging import setup_logging
from tests.utils import build_db_url, build_services


@dataclass
class _StubUser:
    id: int
    username: str | None = None


class _StubBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class _StubMessage:
    def __init__(self, user_id: int, text: str) -> None:
        self.from_user = _StubUser(user_id, "admin")
        self.text = text
        self.bot = _StubBot()
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


def test_next_round_notifies_admins_when_rounds_finished() -> None:
    db_url = build_db_url("rounds_finished_notice")
    services = build_services(db_url)
    tournament_repo = services["tournament_repo"]
    round_repo = services["round_repo"]

    tournament = tournament_repo.get()
    assert tournament is not None
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=1,
        current_round=1,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )
    round_repo.add(Round(id=None, number=1, status=RoundStatus.CLOSED, generated_at=datetime.now(UTC)))

    context = RouterContext(
        config=AppConfig(
            token="123456:abcdefghijklmnopqrstuvwxyzABCDE",
            db_url=db_url,
            admin_ids=[9001],
            arbitrs_ids=[9002],
            timezone="UTC",
            log_level="INFO",
            audit_log_path="logs/test_audit.log",
            default_rules="rules",
            standings_default_top=10,
        ),
        audit_logger=setup_logging(audit_log_path="logs/test_audit.log"),
        acl_service=services["acl_service"],
        notification_service=services["notification_service"],
        scoring_service=services["scoring_service"],
        registration_service=services["registration_service"],
        tournament_service=services["tournament_service"],
        pairing_service=services["pairing_service"],
        result_service=services["result_service"],
        ticket_service=services["ticket_service"],
        undo_service=services["undo_service"],
        player_repo=services["player_repo"],
        round_repo=services["round_repo"],
        game_repo=services["game_repo"],
        table_repo=services["table_repo"],
    )
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "next_round_handler")

    message = _StubMessage(9001, "/next_round")
    with pytest.raises(ValueError, match="Туры завершены"):
        asyncio.run(handler(message))

    assert message.bot.sent
    assert any("завершены" in text.lower() for _, text in message.bot.sent)
