import asyncio
from dataclasses import dataclass

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


def test_start_tournament_resumes_when_round_was_generated_prestart() -> None:
    db_url = build_db_url("start_resume")
    context, services = _build_context(db_url)
    router = build_organizer_router(context)
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "start_tournament_handler")

    tournament_service = services["tournament_service"]
    registration_service = services["registration_service"]
    pairing_service = services["pairing_service"]
    table_repo = services["table_repo"]

    tournament_service.create_tournament()
    table_repo.add(Table(id=None, number=1, location="A"))
    table_repo.add(Table(id=None, number=2, location="B"))
    tournament_service.open_registration()
    tournament_service.set_round_number(2, confirm=True)
    registration_service.register(8101, "u1", "A", 1600)
    registration_service.register(8102, "u2", "B", 1550)
    registration_service.register(8103, "u3", "C", 1500)
    registration_service.register(8104, "u4", "D", 1450)
    tournament_service.prepare_tournament()
    pairing_service.prepare_next_round_preview(1, 9001)
    pairing_service.generate_next_round(1, 9001, allow_prestart=True)

    before_start = tournament_service.ensure_tournament()
    assert before_start.status == TournamentStatus.REGISTRATION
    assert before_start.current_round == 1
    assert len(services["round_repo"].list_all()) == 1

    message = _StubMessage(9001, "/start_tournament")
    asyncio.run(handler(message))

    started = tournament_service.ensure_tournament()
    assert started.status == TournamentStatus.ONGOING
    assert started.current_round == 1
    assert len(services["round_repo"].list_all()) == 1
    assert any("Тур 1:" in text for text in message.answers)
