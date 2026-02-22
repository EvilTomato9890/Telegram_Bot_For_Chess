import pytest

from domain.models import Tournament
from domain.models.enums import TournamentStatus
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


def test_ticket_service_validates_non_empty_payload() -> None:
    service = TicketService(ticket_repository=TicketRepository())

    with pytest.raises(ValueError, match="title cannot be empty"):
        service.create_ticket(author_player_id=1, title="  ", body="body")

    with pytest.raises(ValueError, match="body cannot be empty"):
        service.create_ticket(author_player_id=1, title="title", body=" ")


def test_tournament_service_validates_name() -> None:
    service = TournamentService(tournament_repository=TournamentRepository())

    with pytest.raises(ValueError, match="name cannot be empty"):
        service.create(" ")
