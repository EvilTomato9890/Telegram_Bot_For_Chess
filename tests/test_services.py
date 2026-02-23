from pathlib import Path

import pytest

from domain.models import Tournament
from domain.models.enums import TicketStatus, TournamentStatus
from infra.logging import setup_logging
from repositories import (
    GameRepository,
    PlayerRepository,
    RoundRepository,
    TableRepository,
    TicketRepository,
    TournamentRepository,
)
from services import AccessControlService, PairingService, RegistrationService, TicketService, TournamentService


def test_registration_service_prevents_duplicates() -> None:
    tournament_repository = TournamentRepository()
    tournament = tournament_repository.add(
        Tournament(id=None, name="Cup", status=TournamentStatus.REGISTRATION)
    )
    service = RegistrationService(
        player_repository=PlayerRepository(),
        tournament_repository=tournament_repository,
    )

    service.register_player(tournament.id or 0, telegram_user_id=100, display_name="A")

    with pytest.raises(ValueError, match="already registered"):
        service.register_player(tournament.id or 0, telegram_user_id=100, display_name="A2")


def test_pairing_service_validates_round_and_players() -> None:
    tournament_repository = TournamentRepository()
    tournament = tournament_repository.add(Tournament(id=None, name="Cup", status=TournamentStatus.ONGOING))
    round_repository = RoundRepository()
    service = PairingService(
        tournament_repository=tournament_repository,
        round_repository=round_repository,
        table_repository=TableRepository(),
        game_repository=GameRepository(),
    )

    round_ = service.create_round(tournament.id or 0, number=1)

    with pytest.raises(ValueError, match="players must be different"):
        service.add_game(round_id=round_.id or 0, white_player_id=1, black_player_id=1)

    with pytest.raises(ValueError, match="round not found"):
        service.add_game(round_id=999, white_player_id=1, black_player_id=2)


def test_access_control_service_validates_roles() -> None:
    service = AccessControlService()

    with pytest.raises(ValueError, match="role must be one of"):
        service.grant_role(actor_id=1, target_user_id=2, role="owner")


def test_ticket_service_validates_non_empty_payload(tmp_path: Path) -> None:
    audit_logger = setup_logging(audit_log_path=str(tmp_path / "audit.log"))
    service = TicketService(
        ticket_repository=TicketRepository(),
        audit_logger=audit_logger,
        access_control_service=AccessControlService(config_roles_by_user={11: {"arbiter"}, 99: {"admin"}}),
    )

    with pytest.raises(ValueError, match="description cannot be empty"):
        service.create_ticket(ticket_type="arbitr", author=1, game_id=10, description="  ")


def test_ticket_service_assigns_least_loaded_arbiter(tmp_path: Path) -> None:
    audit_logger = setup_logging(audit_log_path=str(tmp_path / "audit.log"))
    service = TicketService(
        ticket_repository=TicketRepository(),
        audit_logger=audit_logger,
        access_control_service=AccessControlService(config_roles_by_user={2: {"arbiter"}, 3: {"arbiter"}, 99: {"admin"}}),
    )

    first = service.create_ticket(ticket_type="arbitr", author=1, game_id=1, description="a")
    second = service.create_ticket(ticket_type="arbitr", author=1, game_id=2, description="b")

    assert first.assignee_user_id == 2
    assert second.assignee_user_id == 3
    assert first.status == TicketStatus.ASSIGNED




def test_ticket_service_uses_runtime_acl_role_grants_for_assignment(tmp_path: Path) -> None:
    access = AccessControlService(config_roles_by_user={99: {"admin"}})
    access.grant_role(actor_id=99, target_user_id=42, role="arbiter")

    service = TicketService(
        ticket_repository=TicketRepository(),
        audit_logger=setup_logging(audit_log_path=str(tmp_path / "audit.log")),
        access_control_service=access,
    )

    ticket = service.create_ticket(ticket_type="arbitr", author=1, game_id=1, description="needs arbiter")

    assert ticket.assignee_user_id == 42
    assert ticket.status == TicketStatus.ASSIGNED
def test_ticket_service_closes_ticket(tmp_path: Path) -> None:
    audit_logger = setup_logging(audit_log_path=str(tmp_path / "audit.log"))
    service = TicketService(
        ticket_repository=TicketRepository(),
        audit_logger=audit_logger,
        access_control_service=AccessControlService(config_roles_by_user={2: {"arbiter"}, 99: {"admin"}}),
    )

    ticket = service.create_ticket(ticket_type="organizer", author=1, game_id=None, description="need help")
    closed = service.close_ticket(ticket_id=ticket.id or 0, closed_by=99)

    assert closed.status == TicketStatus.CLOSED
    assert closed.closed_by_user_id == 99
    assert closed.closed_at is not None


def test_tournament_service_validates_name() -> None:
    service = TournamentService(tournament_repository=TournamentRepository())

    with pytest.raises(ValueError, match="name cannot be empty"):
        service.create(" ")
