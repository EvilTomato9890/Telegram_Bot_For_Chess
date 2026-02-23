import asyncio
from dataclasses import dataclass

from bot.context import RouterContext
from bot.routers.common import build_common_router
from domain.models import Player
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
        self.from_user = _StubUser(user_id, "u")
        self.text = text
        self.bot = _StubBot()
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


def test_create_ticket_sends_notification_to_assignee() -> None:
    db_url = build_db_url("ticket_notify")
    services = build_services(db_url)
    player_repo = services["player_repo"]
    player_repo.add(Player(id=None, telegram_id=5000, username="author", full_name="Author", rating=1200))

    config = AppConfig(
        token="123456:abcdefghijklmnopqrstuvwxyzABCDE",
        db_url=db_url,
        admin_ids=[9001],
        arbitrs_ids=[9002],
        timezone="UTC",
        log_level="INFO",
        audit_log_path="logs/test_audit.log",
        default_rules="rules",
        standings_default_top=10,
    )
    context = RouterContext(
        config=config,
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
    router = build_common_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "create_ticket_handler")

    message = _StubMessage(5000, "/create_ticket arbitr Нужна помощь")
    asyncio.run(handler(message))

    assert any("Тикет #" in text for text in message.answers)
    assert message.bot.sent
    assignee_id, body = message.bot.sent[0]
    assert assignee_id == 9002
    assert "Новый тикет" in body
