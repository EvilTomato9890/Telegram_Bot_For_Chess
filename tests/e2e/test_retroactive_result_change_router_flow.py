import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from bot.context import RouterContext
from bot.routers.arbitrator import build_arbitrator_router
from domain.models import Game, GameResult, Player, Round, RoundStatus, Table, TournamentStatus
from infra.config import AppConfig
from infra.logging import setup_logging
from tests.utils import ServiceBundle, build_db_url, build_services


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
    def __init__(self, user_id: int, text: str, bot: _StubBot) -> None:
        self.from_user = _StubUser(user_id, f"u{user_id}")
        self.text = text
        self.bot = bot
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


def _bootstrap_prepared_next_round(db_url: str) -> tuple[ServiceBundle, int]:
    services = build_services(db_url)
    tournament_repo = services["tournament_repo"]
    player_repo = services["player_repo"]
    round_repo = services["round_repo"]
    game_repo = services["game_repo"]
    table_repo = services["table_repo"]
    pairing_service = services["pairing_service"]
    scoring_service = services["scoring_service"]

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
    table_repo.add(Table(id=None, number=1, location="A"))
    table_repo.add(Table(id=None, number=2, location="B"))

    p1 = player_repo.add(Player(id=None, telegram_id=8801, username="u1", full_name="A", rating=1600))
    p2 = player_repo.add(Player(id=None, telegram_id=8802, username="u2", full_name="B", rating=1500))
    p3 = player_repo.add(Player(id=None, telegram_id=8803, username="u3", full_name="C", rating=1400))
    p4 = player_repo.add(Player(id=None, telegram_id=8804, username="u4", full_name="D", rating=1300))

    round_row = round_repo.add(Round(id=None, number=1, status=RoundStatus.CLOSED, generated_at=datetime.now(UTC)))
    game_to_change = game_repo.add(
        Game(
            id=None,
            round_id=round_row.id or 0,
            board_number=1,
            white_player_id=p1.id or 0,
            black_player_id=p2.id or 0,
            result=GameResult.WHITE_WIN,
            result_source="arbiter",
        )
    )
    game_repo.add(
        Game(
            id=None,
            round_id=round_row.id or 0,
            board_number=2,
            white_player_id=p3.id or 0,
            black_player_id=p4.id or 0,
            result=GameResult.BLACK_WIN,
            result_source="arbiter",
        )
    )
    scoring_service.recalculate()
    pairing_service.prepare_round(1, 9001)
    return services, game_to_change.id or 0


def _build_context(services: ServiceBundle, db_url: str) -> RouterContext:
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


def test_arbiter_request_sends_confirmation_request_to_admin() -> None:
    db_url = build_db_url("retro_router_request")
    services, game_id = _bootstrap_prepared_next_round(db_url)
    context = _build_context(services, db_url)
    router = build_arbitrator_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "approve_result_handler")

    bot = _StubBot()
    message = _StubMessage(9002, f"/approve_result {game_id} 0.5-0.5", bot)
    asyncio.run(handler(message))

    game_after = services["game_repo"].get_by_id(game_id)
    assert game_after is not None
    assert game_after.result == GameResult.WHITE_WIN
    assert any(chat_id == 9001 and "Команда подтверждения" in text for chat_id, text in bot.sent)
    assert any("Запрос отправлен" in answer or "подготовлен" in answer for answer in message.answers)


def test_admin_confirm_rebuilds_prepared_round_and_notifies_players() -> None:
    db_url = build_db_url("retro_router_confirm")
    services, game_id = _bootstrap_prepared_next_round(db_url)
    context = _build_context(services, db_url)
    router = build_arbitrator_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "approve_result_handler")

    bot = _StubBot()
    message = _StubMessage(9001, f"/approve_result {game_id} 0.5-0.5 confirm", bot)
    asyncio.run(handler(message))

    game_after = services["game_repo"].get_by_id(game_id)
    assert game_after is not None
    assert game_after.result == GameResult.DRAW

    tournament = services["tournament_repo"].get()
    assert tournament is not None
    assert tournament.pending_pairing_payload is not None

    reseed_msgs = [text for chat_id, text in bot.sent if chat_id in {8801, 8802, 8803, 8804} and "Пересборка тура" in text]
    assert len(reseed_msgs) >= 4
    assert any(chat_id == 9001 and "пересобран" in text.lower() for chat_id, text in bot.sent)
    assert any("пересобран" in answer.lower() for answer in message.answers)


def test_admin_without_confirm_gets_explicit_confirmation_hint() -> None:
    db_url = build_db_url("retro_router_admin_hint")
    services, game_id = _bootstrap_prepared_next_round(db_url)
    context = _build_context(services, db_url)
    router = build_arbitrator_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "approve_result_handler")

    bot = _StubBot()
    message = _StubMessage(9001, f"/approve_result {game_id} 0.5-0.5", bot)
    asyncio.run(handler(message))

    game_after = services["game_repo"].get_by_id(game_id)
    assert game_after is not None
    assert game_after.result == GameResult.WHITE_WIN
    assert any("confirm" in answer.lower() for answer in message.answers)
