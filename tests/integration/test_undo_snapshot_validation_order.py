import asyncio
from dataclasses import dataclass
import json

import pytest

from bot.context import RouterContext
from bot.routers.organizer import build_organizer_router
from domain.exceptions import DomainError
from domain.models import Round, RoundStatus, Table, TournamentStatus
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


def _undo_count(services: ServiceBundle) -> int:
    with services["database"].transaction() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM undo_snapshots").fetchone()
    if row is None:
        return 0
    value = row["cnt"]
    return int(value) if value is not None else 0


@pytest.mark.parametrize(
    ("handler_name", "text"),
    [
        ("add_player_handler", "/add_player 123 abc User"),
        ("delete_player_handler", "/delete_player abc"),
        ("disqualify_handler", "/disqualify abc"),
        ("set_player_rating_handler", "/set_player_rating abc 1500"),
    ],
)
def test_invalid_admin_payload_does_not_create_undo_snapshot(handler_name: str, text: str) -> None:
    db_url = build_db_url("undo_parse_order")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == handler_name)
    message = _StubMessage(9001, text)

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_set_round_number_recommendation_error_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_set_round_validation")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    services["tournament_service"].open_registration()
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "set_round_number_handler")
    message = _StubMessage(9001, "/set_round_number 3")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_announce_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_announce_no_snapshot")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "announce_handler")
    message = _StubMessage(9001, "/announce test")

    assert _undo_count(services) == 0
    asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_remove_table_missing_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_remove_table_missing")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "remove_table_handler")
    message = _StubMessage(9001, "/remove_table 2")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_end_round_already_closed_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_end_round_closed")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["tournament_repo"].update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=2,
        current_round=1,
        rules_text="rules",
        pending_pairing_payload=None,
    )
    services["round_repo"].add(Round(id=None, number=1, status=RoundStatus.CLOSED))
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "end_round_handler")
    message = _StubMessage(9001, "/end_round")

    assert _undo_count(services) == 0
    asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_end_round_without_active_round_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_end_round_no_active")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "end_round_handler")
    message = _StubMessage(9001, "/end_round")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_next_round_pending_confirmation_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_next_round_pending")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["tournament_repo"].update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=3,
        current_round=0,
        rules_text="rules",
        pending_pairing_payload=json.dumps(
            {
                "games": [],
                "bye_player_id": None,
                "needs_confirmation": True,
                "reason": "repeat required",
            }
        ),
    )
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "next_round_handler")
    message = _StubMessage(9001, "/next_round")

    assert _undo_count(services) == 0
    asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_confirm_next_round_without_pending_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_confirm_no_pending")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["tournament_repo"].update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=3,
        current_round=0,
        rules_text="rules",
        pending_pairing_payload=None,
    )
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "confirm_next_round_handler")
    message = _StubMessage(9001, "/confirm_next_round")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_disqualify_unknown_player_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_disqualify_unknown")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "disqualify_handler")
    message = _StubMessage(9001, "/disqualify 999")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_set_rating_unknown_player_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_set_rating_unknown")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "set_player_rating_handler")
    message = _StubMessage(9001, "/set_player_rating 999 1500")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_add_table_duplicate_does_not_create_extra_undo_snapshot() -> None:
    db_url = build_db_url("undo_add_table_duplicate")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "add_table_handler")

    assert _undo_count(services) == 0
    asyncio.run(handler(_StubMessage(9001, "/add_table 1 Main Hall")))
    assert _undo_count(services) == 1
    with pytest.raises(DomainError):
        asyncio.run(handler(_StubMessage(9001, "/add_table 1 Main Hall")))
    assert _undo_count(services) == 1


def test_add_player_negative_rating_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_add_player_negative_rating")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "add_player_handler")
    message = _StubMessage(9001, "/add_player 1001 -1 User")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_delete_player_ongoing_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_delete_player_ongoing")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    player = services["registration_service"].add_player_by_admin(
        telegram_id=1001,
        username="u1",
        full_name="User One",
        rating=1200,
    )
    assert player.id is not None
    services["tournament_repo"].update_status(
        TournamentStatus.ONGOING,
        prepared=True,
        number_of_rounds=2,
        current_round=0,
        rules_text="rules",
        pending_pairing_payload=None,
    )
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "delete_player_handler")
    message = _StubMessage(9001, f"/delete_player {player.id}")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0


def test_set_rating_negative_does_not_create_undo_snapshot() -> None:
    db_url = build_db_url("undo_set_rating_negative")
    context, services = _build_context(db_url)
    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    player = services["registration_service"].add_player_by_admin(
        telegram_id=1002,
        username="u2",
        full_name="User Two",
        rating=1300,
    )
    assert player.id is not None
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "set_player_rating_handler")
    message = _StubMessage(9001, f"/set_player_rating {player.id} -10")

    assert _undo_count(services) == 0
    with pytest.raises(DomainError):
        asyncio.run(handler(message))
    assert _undo_count(services) == 0
