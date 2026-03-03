import asyncio
from dataclasses import dataclass

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


class _StubMessage:
    def __init__(self, user_id: int, text: str) -> None:
        self.from_user = _StubUser(user_id, "admin")
        self.text = text
        self.bot = None
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


def test_tournament_status_shows_active_and_disqualified_sections() -> None:
    db_url = build_db_url("status_sections")
    services = build_services(db_url)
    tournament_service = services["tournament_service"]
    registration = services["registration_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A", place_hint="у окна"))
    tournament_service.open_registration()
    p1 = registration.register(7001, "u1", "Active User", 1500)
    p2 = registration.register(7002, "u2", "DQ User", 1400)
    registration.disqualify(p2.id or 0)

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
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "tournament_status_handler")

    message = _StubMessage(9001, "/tournament_status")
    asyncio.run(handler(message))

    body = "\n".join(message.answers)
    assert "active_players=1" in body
    assert "disqualified_players=1" in body
    assert "Active User" in body
    assert "DQ User" in body
    assert "A" in body
    assert p1.id == 1
