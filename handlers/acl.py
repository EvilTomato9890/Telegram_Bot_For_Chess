"""ACL decorators for handlers."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from services import AccessControlService

P = ParamSpec("P")
R = TypeVar("R")


def acl_required(command: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to enforce command-level ACL for handler methods."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not args:
                raise ValueError("handler instance is required")

            self_obj = cast(Any, args[0])
            actor_id = kwargs.get("actor_id")
            if actor_id is None and len(args) >= 2:
                actor_id = args[1]
            if actor_id is None:
                raise ValueError("actor_id is required for ACL check")
            if not isinstance(actor_id, int):
                raise ValueError("actor_id must be an integer")

            access_control_service = cast(AccessControlService, getattr(self_obj, "_access_control_service", None))
            if access_control_service is None:
                raise ValueError("handler does not provide access control service")

            if not access_control_service.can_execute(actor_id, command):
                raise PermissionError(f"access denied for command: {command}")

            return func(*args, **kwargs)

        return wrapper

    return decorator
