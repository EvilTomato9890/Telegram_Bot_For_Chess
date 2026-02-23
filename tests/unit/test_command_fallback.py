import asyncio

from bot.routers.fallback import build_fallback_router


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

