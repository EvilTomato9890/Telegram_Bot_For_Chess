import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from bot.context import RouterContext
from bot.routers.organizer import build_organizer_router
from domain.models import Game, Player, Round, RoundStatus, TournamentStatus
from infra.config import AppConfig
from infra.logging import setup_logging
from tests.utils import ServiceBundle, build_db_url, build_services


@dataclass
class _StubUser:
    id: int
    username: str | None = None


class _StubMessage:
    def __init__(self, user_id: int, text: str) -> None:
        self.from_user = _StubUser(user_id, "user")
        self.text = text
        self.bot = None
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


def _build_context(db_url: str) -> tuple[RouterContext, ServiceBundle]:
    services = build_services(db_url)
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
        player_repo=services["player_repo"],
        round_repo=services["round_repo"],
        game_repo=services["game_repo"],
        table_repo=services["table_repo"],
    )
    return context, services


def _bootstrap_ongoing_with_unfinished_round(services: ServiceBundle) -> None:
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]

    tournament = tournament_repo.get()
    assert tournament is not None
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=3,
        current_round=1,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )
    p1 = player_repo.add(Player(id=None, telegram_id=9201, username="u1", full_name="A", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=9202, username="u2", full_name="B", rating=1450))
    round_row = round_repo.add(Round(id=None, number=1, status=RoundStatus.ONGOING, generated_at=datetime.now(UTC)))
    game_repo.add(
        Game(
            id=None,
            round_id=round_row.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
        )
    )


def test_force_finish_tournament_command_finishes_without_procedures() -> None:
    db_url = build_db_url("force_finish_command")
    context, services = _build_context(db_url)
    _bootstrap_ongoing_with_unfinished_round(services)
    router = build_organizer_router(context)
    handler = next(
        h.callback for h in router.message.handlers if h.callback.__name__ == "force_finish_tournament_handler"
    )

    message = _StubMessage(9001, "/force_finish_tournament")
    asyncio.run(handler(message))

    tournament = services["tournament_repo"].get()
    assert tournament is not None
    assert tournament.status == TournamentStatus.FINISHED
    assert message.answers
    assert "принудительно" in message.answers[-1].lower()


def test_force_finish_tournament_command_is_admin_only() -> None:
    db_url = build_db_url("force_finish_acl")
    context, _services = _build_context(db_url)
    router = build_organizer_router(context)
    handler = next(
        h.callback for h in router.message.handlers if h.callback.__name__ == "force_finish_tournament_handler"
    )

    message = _StubMessage(9002, "/force_finish_tournament")
    with pytest.raises(PermissionError):
        asyncio.run(handler(message))
