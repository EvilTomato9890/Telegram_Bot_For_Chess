import asyncio
from dataclasses import dataclass

from bot.context import RouterContext
from bot.routers.organizer import build_organizer_router
from infra.config import AppConfig
from infra.logging import setup_logging
from tests.utils import ServiceBundle, build_db_url, build_services


@dataclass
class _StubUser:
    id: int
    username: str | None = None


class _StubMessage:
    def __init__(self, user_id: int, text: str) -> None:
        self.from_user = _StubUser(user_id, "admin")
        self.text = text
        self.bot = None
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


def _build_context(db_url: str) -> tuple[RouterContext, ServiceBundle]:
    services = build_services(db_url)
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
    return context, services


def test_add_table_place_hint_is_optional() -> None:
    db_url = build_db_url("add_table_optional")
    context, services = _build_context(db_url)
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "add_table_handler")

    services["tournament_service"].create_tournament()
    message = _StubMessage(9001, "/add_table 1 Главный зал")
    asyncio.run(handler(message))

    table = services["table_repo"].get_by_number(1)
    assert table is not None
    assert table.location == "Главный зал"
    assert table.place_hint is None


def test_add_table_place_hint_with_pipe_parser() -> None:
    db_url = build_db_url("add_table_place_hint")
    context, services = _build_context(db_url)
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "add_table_handler")

    services["tournament_service"].create_tournament()
    message = _StubMessage(9001, "/add_table 2 Сцена | у окна")
    asyncio.run(handler(message))

    table = services["table_repo"].get_by_number(2)
    assert table is not None
    assert table.location == "Сцена"
    assert table.place_hint == "у окна"
