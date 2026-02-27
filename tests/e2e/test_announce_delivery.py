import asyncio
from dataclasses import dataclass

from bot.context import RouterContext
from bot.routers.organizer import build_organizer_router
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


def test_announce_sends_message_to_all_registered_players() -> None:
    db_url = build_db_url("announce_delivery")
    services = build_services(db_url)
    tournament_service = services["tournament_service"]
    registration = services["registration_service"]

    tournament_service.create_tournament()
    tournament_service.open_registration()
    registration.register(8101, "u1", "A", 1500)
    registration.register(8102, "u2", "B", 1400)

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
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "announce_handler")

    message = _StubMessage(9001, "/announce Тестовое объявление")
    asyncio.run(handler(message))

    assert any("Объявление отправлено" in text for text in message.answers)
    sent_ids = {chat_id for chat_id, _ in message.bot.sent}
    assert sent_ids == {8101, 8102}
