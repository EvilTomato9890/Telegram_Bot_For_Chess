import asyncio
from dataclasses import dataclass

from bot.context import RouterContext
from bot.routers.common import build_common_router
from domain.models import Table
from infra.config import AppConfig
from infra.logging import setup_logging
from tests.utils import build_db_url, build_services


@dataclass
class _StubUser:
    id: int
    username: str | None = None


class _StubMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


class _StubCallback:
    def __init__(self, user_id: int) -> None:
        self.from_user = _StubUser(user_id, "user")
        self.message = _StubMessage()
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


class _StubState:
    def __init__(self) -> None:
        self.cleared = 0
        self.set_called = 0

    async def clear(self) -> None:
        self.cleared += 1

    async def set_state(self, _: object) -> None:
        self.set_called += 1

    async def update_data(self, **_: object) -> None:
        return

    async def get_data(self) -> dict[str, object]:
        return {}


def test_unregistered_user_enters_register_flow_when_registration_open() -> None:
    db_url = build_db_url("register_precheck_fsm")
    services = build_services(db_url)
    services["tournament_service"].create_tournament()
    services["table_repo"].add(Table(id=None, number=1, location="A"))
    services["tournament_service"].open_registration()

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
    router = build_common_router(context)
    handler = next(h.callback for h in router.callback_query.handlers if h.callback.__name__ == "start_register_callback")

    callback = _StubCallback(7001)
    state = _StubState()
    asyncio.run(handler(callback, state))

    assert callback.answered is True
    assert state.set_called == 1
    assert callback.message.answers
    assert "1500" in callback.message.answers[-1]

