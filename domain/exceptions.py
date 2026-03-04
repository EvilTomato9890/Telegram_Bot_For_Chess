"""Domain-level exceptions used across services and routers."""

from __future__ import annotations


class DomainError(ValueError):
    """Base class for all domain errors.

    Inherits from ValueError for backward compatibility with existing tests and
    handlers that currently treat user-facing domain issues as ValueError.
    """


class ValidationError(DomainError):
    """Input or business validation failed."""


class CommandFormatError(ValidationError):
    """Command payload has invalid format."""


class NotFoundError(DomainError):
    """Requested domain entity was not found."""


class StateError(DomainError):
    """Operation is not allowed in current domain state."""


class AccessDeniedError(DomainError):
    """Domain-level access restriction."""


class RoundsExhaustedError(StateError):
    """Raised when configured number of rounds is already reached."""


class OrganizerConfirmationRequiredError(StateError):
    """Raised when retroactive result change needs organizer confirmation."""

    def __init__(self, game_id: int, raw_result: str) -> None:
        super().__init__("Требуется подтверждение организатора.")
        self.game_id = game_id
        self.raw_result = raw_result
