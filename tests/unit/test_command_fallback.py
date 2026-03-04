import asyncio

import pytest

from bot.routers.fallback import build_fallback_router
from tests.utils import build_db_url, build_services


class _StubMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []
        self.text = "/unknown"

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


def test_unknown_command_returns_help_hint() -> None:
    router = build_fallback_router()
    handler = router.message.handlers[0].callback
    message = _StubMessage()
    asyncio.run(handler(message))
    assert message.answers == ["Команда не распознана. Используйте /help"]


def test_unregistered_denied_command_has_register_hint() -> None:
    services = build_services(build_db_url("fallback_acl_unregistered"))
    acl = services["acl_service"]

    with pytest.raises(PermissionError, match=r"Команда недоступна до регистрации\. Используйте /register\."):
        acl.require(777777, "/rules")
