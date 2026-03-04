import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from bot.context import RouterContext
from bot.routers.organizer import build_organizer_router
from domain.models import Table
from infra.config import AppConfig
from infra.logging import setup_logging
from tests.utils import build_db_url, build_services


@dataclass
class _StubUser:
    id: int
    username: str | None = None


class _StubBot:
    async def get_chat(self, chat_id: str) -> SimpleNamespace:
        assert chat_id == "@resolved_user"
        return SimpleNamespace(id=712345, username="resolved_user")

    async def send_message(self, chat_id: int, text: str) -> None:  # pragma: no cover
        return


class _StubMessage:
    def __init__(self, user_id: int, text: str) -> None:
        self.from_user = _StubUser(user_id, "admin")
        self.text = text
        self.bot = _StubBot()
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


def test_add_player_resolves_username_via_bot_get_chat() -> None:
    db_url = build_db_url("add_player_username")
    services = build_services(db_url)
    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
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
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "add_player_handler")
    message = _StubMessage(9001, "/add_player @resolved_user 1725 Test User")

    asyncio.run(handler(message))

    player = services["player_repo"].get_by_telegram_id(712345)
    assert player is not None
    assert player.username == "resolved_user"
    assert player.rating == 1725
