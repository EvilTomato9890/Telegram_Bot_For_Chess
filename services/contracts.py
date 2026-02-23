"""Service layer for tournament operations and role management."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from domain.models import Game, Player, Round, Ticket, Tournament
from domain.models.enums import TicketStatus, TicketType, TournamentStatus
from infra.logging import AuditLogger
from repositories import (
    GameRepository,
    PlayerRepository,
    RoundRepository,
    TableRepository,
    TicketRepository,
    TournamentRepository,
)

from .access_control import AccessControlService
from .scoring import ScoringService



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


class TicketService:
    """Create and track support tickets."""

    def __init__(
        self,
        ticket_repository: TicketRepository,
        audit_logger: AuditLogger,
        access_control_service: AccessControlService,
    ) -> None:
        self._ticket_repository = ticket_repository
        self._audit_logger = audit_logger
        self._access_control_service = access_control_service

    def create_ticket(self, ticket_type: str, author: int, game_id: int | None, description: str) -> Ticket:
        normalized_description = description.strip()
        if not normalized_description:
            raise ValueError("ticket description cannot be empty")

        normalized_type = TicketType(ticket_type.strip().lower())
        assignee_user_id = self._pick_assignee(normalized_type)
        status = TicketStatus.ASSIGNED if assignee_user_id is not None else TicketStatus.OPEN

        ticket = self._ticket_repository.add(
            Ticket(
                id=None,
                author_player_id=author,
                ticket_type=normalized_type,
                status=status,
                assignee_user_id=assignee_user_id,
                game_id=game_id,
                description=normalized_description,
            )
        )
        self._audit_logger.log_event(
            actor=str(author),
            command="/create_ticket",
            entity=f"ticket:{ticket.id}",
            action=(
                f"created type={ticket.ticket_type.value} assignee={assignee_user_id}"
                if assignee_user_id is not None
                else f"created type={ticket.ticket_type.value} assignee=none"
            ),
            result="ok",
        )
        return ticket

    def close_ticket(self, ticket_id: int, closed_by: int) -> Ticket:
        ticket = self._ticket_repository.get(ticket_id)
        if ticket is None:
            raise ValueError("ticket not found")
        if ticket.status == TicketStatus.CLOSED:
            raise ValueError("ticket is already closed")

        closed_ticket = self._ticket_repository.update(
            Ticket(
                id=ticket.id,
                author_player_id=ticket.author_player_id,
                ticket_type=ticket.ticket_type,
                status=TicketStatus.CLOSED,
                assignee_user_id=ticket.assignee_user_id,
                game_id=ticket.game_id,
                description=ticket.description,
                closed_by_user_id=closed_by,
                closed_at=datetime.now(UTC),
            )
        )
        self._audit_logger.log_event(
            actor=str(closed_by),
            command="/close_ticket",
            entity=f"ticket:{ticket_id}",
            action="closed",
            result="ok",
        )
        return closed_ticket

    def _pick_assignee(self, ticket_type: TicketType) -> int | None:
        role = "arbiter" if ticket_type == TicketType.ARBITR else "admin"
        candidates = self._access_control_service.user_ids_with_role(role)
        if not candidates:
            return None

        return min(
            candidates,
            key=lambda user_id: (self._ticket_repository.active_count_by_assignee(user_id), user_id),
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




__all__ = [
    "TournamentService",
    "RegistrationService",
    "PairingService",
    "ScoringService",
    "TicketService",
    "NotificationService",
    "AccessControlService",
]
