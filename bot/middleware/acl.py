"""ACL middleware helpers for aiogram command handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from aiogram.types import Message

from services import AccessControlService

P = ParamSpec("P")
R = TypeVar("R")


def require_acl(command_name: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator enforcing command-level ACL checks."""

    def decorator(handler: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(handler)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not args:
                raise ValueError("missing handler arguments")
            message: Message | None = None
            for value in args:
                if isinstance(value, Message):
                    message = value
                    break
            if message is None:
                maybe_message = kwargs.get("message")
                if isinstance(maybe_message, Message):
                    message = maybe_message
            if message is None or message.from_user is None:
                raise ValueError("cannot resolve actor from message")
            context = cast(dict[str, Any], kwargs.get("context", {}))
            acl = context.get("acl_service")
            if not isinstance(acl, AccessControlService):
                raise ValueError("acl_service is missing in handler context")
            if not acl.can_execute(message.from_user.id, command_name):
                await message.answer("Недостаточно прав для этой команды.")
                raise PermissionError("acl denied")
            return await handler(*args, **kwargs)

        return wrapper

    return decorator

