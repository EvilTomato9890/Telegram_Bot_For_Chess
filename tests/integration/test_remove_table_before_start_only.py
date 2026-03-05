import asyncio
from dataclasses import dataclass

import pytest

from bot.context import RouterContext
from bot.routers.organizer import build_organizer_router
from domain.models import Table, TournamentStatus
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
        player_repo=services["player_repo"],
        round_repo=services["round_repo"],
        game_repo=services["game_repo"],
        table_repo=services["table_repo"],
    )
    return context, services


def test_remove_table_is_allowed_before_tournament_start() -> None:
    db_url = build_db_url("remove_table_before_start")
    context, services = _build_context(db_url)
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "remove_table_handler")

    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))

    message = _StubMessage(9001, "/remove_table 1")
    asyncio.run(handler(message))

    assert services["table_repo"].get_by_number(1) is None
    assert any("удален" in text.lower() for text in message.answers)


def test_remove_table_is_forbidden_after_tournament_start() -> None:
    db_url = build_db_url("remove_table_after_start")
    context, services = _build_context(db_url)
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "remove_table_handler")

    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    tournament = services["tournament_repo"].get()
    assert tournament is not None
    services["tournament_repo"].update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=2,
        current_round=0,
        rules_text=tournament.rules_text,
        pending_pairing_payload=None,
    )

    with pytest.raises(ValueError, match="только до старта турнира"):
        asyncio.run(handler(_StubMessage(9001, "/remove_table 1")))

    assert services["table_repo"].get_by_number(1) is not None


def test_remove_table_before_start_invalidates_prepared_pairs() -> None:
    db_url = build_db_url("remove_table_invalidates_pending")
    context, services = _build_context(db_url)
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "remove_table_handler")

    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    table_repo = services["table_repo"]
    pairing_service = services["pairing_service"]
    tournament_repo = services["tournament_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    table_repo.add(Table(id=None, number=2, location="B"))
    tournament_service.open_registration()
    tournament_service.set_round_number(2, confirm=True)
    registration_service.register(12101, "u1", "A", 1600)
    registration_service.register(12102, "u2", "B", 1500)
    registration_service.register(12103, "u3", "C", 1400)
    registration_service.register(12104, "u4", "D", 1300)
    tournament_service.prepare_tournament()
    pairing_service.prepare_next_round_preview(1, 9001)

    before = tournament_repo.get()
    assert before is not None
    assert before.pending_pairing_payload is not None

    message = _StubMessage(9001, "/remove_table 1")
    asyncio.run(handler(message))

    after = tournament_repo.get()
    assert after is not None
    assert after.pending_pairing_payload is None
    assert any("сброшены" in text.lower() for text in message.answers)
