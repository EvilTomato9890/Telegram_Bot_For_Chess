"""Player registration and roster management."""

from __future__ import annotations

from datetime import UTC, datetime

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

        tournament = self._require_tournament()
        if tournament.status != TournamentStatus.REGISTRATION or tournament.prepared:
            raise ValueError("Регистрация закрыта.")
        self._ensure_capacity_limit(new_player=True)

        if self._player_repo.get_by_telegram_id(telegram_id) is not None:
            raise ValueError("Игрок уже зарегистрирован.")
        if rating < 0:
            raise ValueError("Рейтинг не может быть отрицательным.")
        if not full_name.strip():
            raise ValueError("Имя игрока не может быть пустым.")

        return self._player_repo.add(
            Player(
                id=None,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name.strip(),
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
        rating: int = 0,
    ) -> Player:
        """Admin command to append participant."""

        tournament = self._require_tournament()
        if tournament.status not in {TournamentStatus.DRAFT, TournamentStatus.REGISTRATION}:
            raise ValueError("Добавление игроков доступно только до старта турнира.")
        self._ensure_capacity_limit(new_player=True)
        existing = self._player_repo.get_by_telegram_id(telegram_id)
        if existing is not None:
            raise ValueError("Игрок с таким telegram_id уже существует.")
        return self._player_repo.add(
            Player(
                id=None,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name.strip(),
                rating=rating,
                status=PlayerStatus.ACTIVE,
                created_at=datetime.now(UTC),
            )
        )

    def disqualify(self, player_id: int) -> Player:
        """Mark player as disqualified."""

        player = self._player_repo.get_by_id(player_id)
        if player is None:
            raise ValueError("Игрок не найден.")
        player.status = PlayerStatus.DISQUALIFIED
        return self._player_repo.update(player)

    def set_rating(self, player_id: int, rating: int) -> Player:
        """Update player rating if tournament is not prepared."""

        tournament = self._require_tournament()
        if tournament.prepared:
            raise ValueError("После /prepare_tournament менять рейтинг запрещено.")
        player = self._player_repo.get_by_id(player_id)
        if player is None:
            raise ValueError("Игрок не найден.")
        if rating < 0:
            raise ValueError("Рейтинг не может быть отрицательным.")
        player.rating = rating
        return self._player_repo.update(player)

    def all_players(self) -> list[Player]:
        """Return complete player list."""

        return self._player_repo.list_all()

    def _ensure_capacity_limit(self, *, new_player: bool) -> None:
        tables = self._table_repo.list_all()
        if not tables:
            return
        limit = len(tables) * 2
        projected = len(self._player_repo.list_all()) + (1 if new_player else 0)
        if projected > limit:
            raise ValueError(
                f"Лимит участников превышен: столов {len(tables)}, максимум игроков {limit}."
            )

    def _require_tournament(self) -> Tournament:
        tournament = self._tournament_repo.get()
        if tournament is None:
            raise ValueError("Турнир еще не создан. Используйте /create_tournament.")
        return tournament

