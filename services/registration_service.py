"""Player registration and roster management."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.exceptions import DomainError
from domain.models import Player, PlayerStatus, Tournament, TournamentStatus
from repositories import PlayerRepository, TableRepository, TournamentRepository


class RegistrationService:
    """Manage registration and player state changes."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        tournament_repo: TournamentRepository,
        table_repo: TableRepository,
    ) -> None:
        self._player_repo = player_repo
        self._tournament_repo = tournament_repo
        self._table_repo = table_repo

    def register(self, telegram_id: int, username: str | None, full_name: str, rating: int) -> Player:
        """Register one participant during registration period."""

        self.validate_self_registration_precheck(telegram_id)
        if rating < 0:
            raise DomainError("Рейтинг не может быть отрицательным.")
        normalized_name = full_name.strip()
        if not normalized_name:
            raise DomainError("Имя игрока не может быть пустым.")

        return self._player_repo.add(
            Player(
                id=None,
                telegram_id=telegram_id,
                username=username,
                full_name=normalized_name,
                rating=rating,
                status=PlayerStatus.ACTIVE,
                created_at=datetime.now(UTC),
            )
        )

    def add_player_by_admin(
        self,
        telegram_id: int,
        username: str | None,
        full_name: str,
        rating: int,
    ) -> Player:
        """Admin command to append participant."""

        self.validate_admin_add_precheck()
        existing = self._player_repo.get_by_telegram_id(telegram_id)
        if existing is not None:
            raise DomainError("Игрок с таким telegram_id уже существует.")
        if rating < 0:
            raise DomainError("Рейтинг не может быть отрицательным.")
        normalized_name = full_name.strip()
        if not normalized_name:
            raise DomainError("Имя игрока не может быть пустым.")
        return self._player_repo.add(
            Player(
                id=None,
                telegram_id=telegram_id,
                username=username,
                full_name=normalized_name,
                rating=rating,
                status=PlayerStatus.ACTIVE,
                created_at=datetime.now(UTC),
            )
        )

    def disqualify(self, player_id: int) -> Player:
        """Mark player as disqualified."""

        player = self._player_repo.get_by_id(player_id)
        if player is None:
            raise DomainError("Игрок не найден.")
        player.status = PlayerStatus.DISQUALIFIED
        return self._player_repo.update(player)

    def delete_player_by_admin(self, player_id: int) -> Player:
        """Delete player from roster before tournament start."""

        tournament = self._require_tournament()
        if tournament.status not in {TournamentStatus.DRAFT, TournamentStatus.REGISTRATION} or tournament.prepared:
            raise DomainError("Удалять игрока можно только до старта турнира.")
        player = self._player_repo.get_by_id(player_id)
        if player is None:
            raise DomainError("Игрок не найден.")
        if not self._player_repo.delete_by_id(player_id):
            raise DomainError("Не удалось удалить игрока.")
        return player

    def set_rating(self, player_id: int, rating: int) -> Player:
        """Update player rating if tournament is not prepared."""

        tournament = self._require_tournament()
        if tournament.prepared:
            raise DomainError("После /prepare_tournament менять рейтинг запрещено.")
        player = self._player_repo.get_by_id(player_id)
        if player is None:
            raise DomainError("Игрок не найден.")
        if rating < 0:
            raise DomainError("Рейтинг не может быть отрицательным.")
        player.rating = rating
        return self._player_repo.update(player)

    def all_players(self) -> list[Player]:
        """Return complete player list."""

        return self._player_repo.list_all()

    def validate_self_registration_precheck(self, telegram_id: int) -> None:
        """Validate non-input registration constraints before asking for form fields."""

        tournament = self._require_tournament()
        if tournament.status != TournamentStatus.REGISTRATION or tournament.prepared:
            raise DomainError("Регистрация закрыта.")
        self._ensure_capacity_limit(new_player=True)
        if self._player_repo.get_by_telegram_id(telegram_id) is not None:
            raise DomainError("Вы уже зарегистрированы.")

    def validate_admin_add_precheck(self) -> None:
        """Validate admin roster constraints before parsing command payload."""

        tournament = self._require_tournament()
        if tournament.status not in {TournamentStatus.DRAFT, TournamentStatus.REGISTRATION} or tournament.prepared:
            raise DomainError("Добавление игроков доступно только до старта турнира.")
        self._ensure_capacity_limit(new_player=True)

    def _ensure_capacity_limit(self, *, new_player: bool) -> None:
        tables = self._table_repo.list_all()
        if not tables:
            raise DomainError("Сначала добавьте столы: регистрация недоступна без столов.")
        limit = len(tables) * 2
        projected = self._count_active_players() + (1 if new_player else 0)
        if projected > limit:
            raise DomainError(
                f"Лимит участников превышен: столов {len(tables)}, максимум игроков {limit}."
            )

    def _count_active_players(self) -> int:
        return sum(1 for player in self._player_repo.list_all() if player.status == PlayerStatus.ACTIVE)

    def _require_tournament(self) -> Tournament:
        tournament = self._tournament_repo.get()
        if tournament is None:
            raise DomainError("Турнир еще не создан. Используйте /create_tournament.")
        return tournament
