"""Service layer for tournament operations and role management."""

from __future__ import annotations

from dataclasses import replace

from domain.models import Game, Player, Round, Ticket, Tournament
from domain.models.enums import TicketStatus, TicketType, TournamentStatus
from repositories import (
    GameRepository,
    PlayerRepository,
    RoundRepository,
    TableRepository,
    TicketRepository,
    TournamentRepository,
)
from schemas import ServiceResponse
from validators import validate_role

_VALID_RESULTS = {"1-0", "0-1", "0.5-0.5", "bye", "forfeit"}


class TournamentService:
    """Manage tournament lifecycle commands."""

    _ALLOWED_TRANSITIONS: dict[TournamentStatus, set[TournamentStatus]] = {
        TournamentStatus.DRAFT: {TournamentStatus.REGISTRATION},
        TournamentStatus.REGISTRATION: {TournamentStatus.ONGOING},
        TournamentStatus.ONGOING: {TournamentStatus.FINISHED},
        TournamentStatus.FINISHED: set(),
    }

    def __init__(self, tournament_repository: TournamentRepository) -> None:
        self._tournament_repository = tournament_repository

    def create(self, name: str) -> Tournament:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("tournament name cannot be empty")
        return self._tournament_repository.add(Tournament(id=None, name=normalized_name))

    def change_status(self, tournament_id: int, status: TournamentStatus) -> Tournament:
        tournament = self._require_tournament(tournament_id)
        if status not in self._ALLOWED_TRANSITIONS[tournament.status]:
            raise ValueError(f"invalid transition: {tournament.status} -> {status}")

        updated = replace(tournament, status=status)
        return self._tournament_repository.update(updated)

    def _require_tournament(self, tournament_id: int) -> Tournament:
        tournament = self._tournament_repository.get(tournament_id)
        if tournament is None:
            raise ValueError("tournament not found")
        return tournament


class RegistrationService:
    """Manage player registration operations."""

    def __init__(self, player_repository: PlayerRepository, tournament_repository: TournamentRepository) -> None:
        self._player_repository = player_repository
        self._tournament_repository = tournament_repository

    def register_player(self, tournament_id: int, telegram_user_id: int, display_name: str) -> Player:
        tournament = self._tournament_repository.get(tournament_id)
        if tournament is None:
            raise ValueError("tournament not found")
        if tournament.status != TournamentStatus.REGISTRATION:
            raise ValueError("registration is available only in registration status")

        if any(
            player.telegram_user_id == telegram_user_id
            for player in self._player_repository.list_by_tournament(tournament_id)
        ):
            raise ValueError("player is already registered in this tournament")

        normalized_display_name = display_name.strip()
        if not normalized_display_name:
            raise ValueError("display_name cannot be empty")

        return self._player_repository.add(
            Player(
                id=None,
                tournament_id=tournament_id,
                telegram_user_id=telegram_user_id,
                display_name=normalized_display_name,
            )
        )


class PairingService:
    """Create rounds and pairings for ongoing tournaments."""

    def __init__(
        self,
        tournament_repository: TournamentRepository,
        round_repository: RoundRepository,
        table_repository: TableRepository,
        game_repository: GameRepository,
    ) -> None:
        self._tournament_repository = tournament_repository
        self._round_repository = round_repository
        self._table_repository = table_repository
        self._game_repository = game_repository

    def create_round(self, tournament_id: int, number: int) -> Round:
        if number <= 0:
            raise ValueError("round number must be positive")

        tournament = self._tournament_repository.get(tournament_id)
        if tournament is None:
            raise ValueError("tournament not found")
        if tournament.status != TournamentStatus.ONGOING:
            raise ValueError("pairings can be generated only in ongoing status")

        if any(round_.number == number for round_ in self._round_repository.list_by_tournament(tournament_id)):
            raise ValueError("round with this number already exists")

        return self._round_repository.add(Round(id=None, tournament_id=tournament_id, number=number))

    def add_game(self, round_id: int, white_player_id: int, black_player_id: int) -> Game:
        round_ = self._round_repository.get(round_id)
        if round_ is None:
            raise ValueError("round not found")
        if white_player_id == black_player_id:
            raise ValueError("players must be different")

        tables = self._table_repository.list_by_round(round_id)
        table_id = tables[0].id if tables else None
        return self._game_repository.add(
            Game(
                id=None,
                round_id=round_id,
                table_id=table_id,
                white_player_id=white_player_id,
                black_player_id=black_player_id,
            )
        )


class ScoringService:
    """Validate and register game results."""

    def validate_result(self, result: str) -> str:
        if result not in _VALID_RESULTS:
            raise ValueError("invalid result token")
        return result


class TicketService:
    """Create and track support tickets."""

    def __init__(self, ticket_repository: TicketRepository) -> None:
        self._ticket_repository = ticket_repository

    def create_ticket(self, author_player_id: int, title: str, body: str) -> Ticket:
        normalized_title = title.strip()
        normalized_body = body.strip()
        if not normalized_title:
            raise ValueError("ticket title cannot be empty")
        if not normalized_body:
            raise ValueError("ticket body cannot be empty")

        return self._ticket_repository.add(
            Ticket(
                id=None,
                author_player_id=author_player_id,
                ticket_type=TicketType.OTHER,
                status=TicketStatus.OPEN,
                title=normalized_title,
                body=normalized_body,
            )
        )


class NotificationService:
    """Collect bot notifications for delivery adapters."""

    def __init__(self) -> None:
        self._outbox: list[str] = []

    def notify(self, message: str) -> None:
        self._outbox.append(message)

    def flush(self) -> list[str]:
        messages = [*self._outbox]
        self._outbox.clear()
        return messages


class AccessControlService:
    """Role grants/revokes and permissions checks."""

    def __init__(self) -> None:
        self._roles_by_user: dict[int, set[str]] = {}

    def grant_role(self, actor_id: int, target_user_id: int, role: str) -> ServiceResponse:
        del actor_id
        normalized_role = validate_role(role)
        roles = self._roles_by_user.setdefault(target_user_id, set())
        roles.add(normalized_role)
        return ServiceResponse(ok=True, message=f"role '{normalized_role}' granted to user {target_user_id}")

    def revoke_role(self, actor_id: int, target_user_id: int, role: str) -> ServiceResponse:
        del actor_id
        normalized_role = validate_role(role)
        roles = self._roles_by_user.setdefault(target_user_id, set())
        roles.discard(normalized_role)
        return ServiceResponse(ok=True, message=f"role '{normalized_role}' revoked for user {target_user_id}")

    def has_role(self, user_id: int, role: str) -> bool:
        normalized_role = validate_role(role)
        return normalized_role in self._roles_by_user.get(user_id, set())


__all__ = [
    "TournamentService",
    "RegistrationService",
    "PairingService",
    "ScoringService",
    "TicketService",
    "NotificationService",
    "AccessControlService",
]
