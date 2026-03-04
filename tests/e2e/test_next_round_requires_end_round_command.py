import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from bot.context import RouterContext
from bot.routers.organizer import build_organizer_router
from domain.models import Game, Player, Round, RoundStatus, TournamentStatus
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


def _build_context(db_url: str) -> RouterContext:
    services = build_services(db_url)
    return RouterContext(
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


def _bootstrap_round_with_finished_game(db_url: str) -> None:
    services = build_services(db_url)
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    result_service = services["result_service"]

    tournament = tournament_repo.get()
    assert tournament is not None
    tournament_repo.update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=2,
        current_round=1,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )
    p1 = player_repo.add(Player(id=None, telegram_id=8601, username="u1", full_name="A", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=8602, username="u2", full_name="B", rating=1450))
    round_row = round_repo.add(Round(id=None, number=1, status=RoundStatus.ONGOING, generated_at=datetime.now(UTC)))
    game = game_repo.add(
        Game(
            id=None,
            round_id=round_row.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
        )
    )
    result_service.approve_result(game.id or 0, "1-0")


def test_next_round_command_is_blocked_until_end_round() -> None:
    db_url = build_db_url("next_round_requires_end_round")
    _bootstrap_round_with_finished_game(db_url)
    context = _build_context(db_url)
    router = build_organizer_router(context)
    next_round_handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "next_round_handler")

    message = _StubMessage(9001, "/next_round")
    with pytest.raises(ValueError):
        asyncio.run(next_round_handler(message))

    round_after = context.round_repo.get_by_number(1)
    assert round_after is not None
    assert round_after.status == RoundStatus.ONGOING


def test_end_round_command_closes_finished_round() -> None:
    db_url = build_db_url("end_round_command_closes")
    _bootstrap_round_with_finished_game(db_url)
    context = _build_context(db_url)
    router = build_organizer_router(context)
    end_round_handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "end_round_handler")

    message = _StubMessage(9001, "/end_round")
    asyncio.run(end_round_handler(message))

    round_after = context.round_repo.get_by_number(1)
    assert round_after is not None
    assert round_after.status == RoundStatus.CLOSED
