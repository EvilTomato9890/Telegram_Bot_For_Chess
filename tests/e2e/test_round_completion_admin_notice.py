import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from bot.context import RouterContext
from bot.routers.common import build_common_router
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
    def __init__(self, bot: _StubBot) -> None:
        self.bot = bot
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


class _StubCallback:
    def __init__(self, user_id: int, data: str, bot: _StubBot) -> None:
        self.from_user = _StubUser(user_id, f"u{user_id}")
        self.data = data
        self.message = _StubMessage(bot)
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


def test_report_closes_round_and_notifies_admins() -> None:
    db_url = build_db_url("round_completion_notice")
    services = build_services(db_url)
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
    p1 = player_repo.add(Player(id=None, telegram_id=8101, username="u1", full_name="A", rating=1500))
    p2 = player_repo.add(Player(id=None, telegram_id=8102, username="u2", full_name="B", rating=1450))
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
    router = build_common_router(context)
    handler = next(h.callback for h in router.callback_query.handlers if h.callback.__name__ == "report_callback_handler")

    bot = _StubBot()
    first = _StubCallback(8101, "report:white", bot)
    second = _StubCallback(8102, "report:white", bot)

    asyncio.run(handler(first))
    assert not any(chat_id == 9001 for chat_id, _ in bot.sent)

    asyncio.run(handler(second))
    admin_notices = [text for chat_id, text in bot.sent if chat_id == 9001 and "/end_round" in text]
    assert len(admin_notices) == 1
    assert "1" in admin_notices[0]
    round_after = services["round_repo"].get_by_number(1)
    assert round_after is not None
    assert round_after.status == RoundStatus.ONGOING
