"""Tournament lifecycle management."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import math

from domain.models import RoundStatus, Table, Tournament, TournamentStatus
from repositories import (
    GameReportRepository,
    GameRepository,
    PlayerRepository,
    RoundRepository,
    TableRepository,
    TicketRepository,
    TournamentRepository,
)


class TournamentService:
    """Manage tournament status transitions and settings."""

    def __init__(
        self,
        tournament_repo: TournamentRepository,
        table_repo: TableRepository,
        round_repo: RoundRepository,
        player_repo: PlayerRepository,
        game_repo: GameRepository,
        ticket_repo: TicketRepository,
        report_repo: GameReportRepository,
        *,
        default_rules: str,
    ) -> None:
        self._tournament_repo = tournament_repo
        self._table_repo = table_repo
        self._round_repo = round_repo
        self._player_repo = player_repo
        self._game_repo = game_repo
        self._ticket_repo = ticket_repo
        self._report_repo = report_repo
        self._default_rules = default_rules

    def ensure_tournament(self) -> Tournament:
        """Create default tournament row when absent."""

        return self._tournament_repo.ensure_exists(default_rules=self._default_rules)

    def create_tournament(self, number_of_tables: int) -> Tournament:
        """Reset tournament into draft with predefined number of tables."""

        if number_of_tables <= 0:
            raise ValueError("Число столов должно быть положительным.")

        tournament = self.ensure_tournament()
        updated = replace(
            tournament,
            status=TournamentStatus.DRAFT,
            number_of_rounds=0,
            current_round=0,
            prepared=False,
            pending_pairing_payload=None,
            updated_at=datetime.now(UTC),
        )
        stored = self._tournament_repo.upsert(updated)

        # Reset tournament runtime state.
        with self._player_repo._database.transaction() as conn:  # noqa: SLF001
            self._report_repo.clear_all(conn)
            self._game_repo.clear_all(conn)
            self._round_repo.clear_all(conn)
            self._ticket_repo.clear_all(conn)
            self._player_repo.clear_all(conn)
            conn.execute("DELETE FROM tables")

        # Tables are global for tournament lifecycle; recreate from scratch.
        existing_tables = self._table_repo.list_all()
        for table in existing_tables:
            self._table_repo.remove_by_number(table.number)
        for number in range(1, number_of_tables + 1):
            self._table_repo.add(Table(id=None, number=number, location=f"Стол {number}", place_hint=None))

        return stored

    def open_registration(self) -> Tournament:
        """Move tournament from draft to registration."""

        tournament = self.ensure_tournament()
        if tournament.status != TournamentStatus.DRAFT:
            raise ValueError("Открыть регистрацию можно только из статуса draft.")
        player_count = self._count_players()
        max_capacity = len(self._table_repo.list_all()) * 2
        if max_capacity and player_count > max_capacity:
            raise ValueError("Игроков уже больше чем 2 * число столов.")
        return self._tournament_repo.update_status(TournamentStatus.REGISTRATION, prepared=False)

    def set_round_number(self, rounds: int, *, confirm: bool) -> tuple[Tournament, int]:
        """Set number of rounds with recommendation check."""

        if rounds <= 0:
            raise ValueError("Число туров должно быть положительным.")
        tournament = self.ensure_tournament()
        if tournament.status not in {TournamentStatus.DRAFT, TournamentStatus.REGISTRATION}:
            raise ValueError("Число туров можно менять только до старта турнира.")
        recommendation = self.round_recommendation(self._count_active_players())
        if rounds != recommendation and not confirm:
            raise ValueError(
                f"Рекомендованное число туров: {recommendation}. "
                f"Повторите команду с confirm для подтверждения."
            )
        updated = self._tournament_repo.update_status(
            tournament.status,
            number_of_rounds=rounds,
            prepared=tournament.prepared,
            current_round=tournament.current_round,
            rules_text=tournament.rules_text,
            pending_pairing_payload=tournament.pending_pairing_payload,
        )
        return updated, recommendation

    def set_rules(self, text: str) -> Tournament:
        """Persist tournament rules text."""

        if not text.strip():
            raise ValueError("Текст правил не может быть пустым.")
        tournament = self.ensure_tournament()
        return self._tournament_repo.update_status(
            tournament.status,
            number_of_rounds=tournament.number_of_rounds,
            prepared=tournament.prepared,
            current_round=tournament.current_round,
            rules_text=text.strip(),
            pending_pairing_payload=tournament.pending_pairing_payload,
        )

    def prepare_tournament(self) -> Tournament:
        """Lock registration and mark tournament as prepared."""

        tournament = self.ensure_tournament()
        if tournament.status != TournamentStatus.REGISTRATION:
            raise ValueError("Подготовка доступна только в статусе registration.")
        return self._tournament_repo.update_status(
            TournamentStatus.REGISTRATION,
            prepared=True,
            number_of_rounds=tournament.number_of_rounds,
            current_round=tournament.current_round,
            rules_text=tournament.rules_text,
            pending_pairing_payload=tournament.pending_pairing_payload,
        )

    def start_tournament(self) -> Tournament:
        """Move tournament to ongoing status."""

        tournament = self.ensure_tournament()
        if tournament.status != TournamentStatus.REGISTRATION:
            raise ValueError("Турнир можно стартовать только из registration.")
        if not tournament.prepared:
            raise ValueError("Сначала выполните /prepare_turnament.")
        if tournament.number_of_rounds <= 0:
            raise ValueError("Сначала задайте число туров через /set_round_number.")
        if self._count_active_players() < 2:
            raise ValueError("Для старта нужно минимум 2 активных игрока.")
        return self._tournament_repo.update_status(
            TournamentStatus.ONGOING,
            prepared=True,
            number_of_rounds=tournament.number_of_rounds,
            current_round=0,
            rules_text=tournament.rules_text,
            pending_pairing_payload=None,
        )

    def end_current_round(self) -> None:
        """Close current round when all its games have results."""

        current = self._round_repo.get_current()
        if current is None:
            tournament = self.ensure_tournament()
            if tournament.current_round <= 0:
                raise ValueError("Нет активного тура.")
            closed_round = self._round_repo.get_by_number(tournament.current_round)
            if closed_round is not None and closed_round.status == RoundStatus.CLOSED:
                return
            current = closed_round
        if current is None:
            raise ValueError("Нет активного тура.")
        if current.status == RoundStatus.CLOSED:
            return
        games = self._game_repo.list_by_round(current.id or 0)
        if not games or any(game.result is None for game in games):
            raise ValueError("Нельзя закрыть тур: не все результаты зафиксированы.")
        current.status = RoundStatus.CLOSED
        current.closed_at = datetime.now(UTC)
        self._round_repo.update(current)

    def finish_tournament(self) -> Tournament:
        """Mark tournament as finished."""

        tournament = self.ensure_tournament()
        if tournament.status != TournamentStatus.ONGOING:
            raise ValueError("Завершение доступно только для ongoing турнира.")
        current = self._round_repo.get_current()
        if current is not None and current.status != RoundStatus.CLOSED:
            raise ValueError("Сначала закройте текущий тур.")
        return self._tournament_repo.update_status(
            TournamentStatus.FINISHED,
            prepared=tournament.prepared,
            number_of_rounds=tournament.number_of_rounds,
            current_round=tournament.current_round,
            rules_text=tournament.rules_text,
            pending_pairing_payload=None,
        )

    def status_summary(self) -> dict[str, object]:
        """Build human-readable tournament status payload."""

        tournament = self.ensure_tournament()
        tables = self._table_repo.list_all()
        active_players = self._count_active_players()
        return {
            "status": tournament.status.value,
            "rounds_total": tournament.number_of_rounds,
            "round_current": tournament.current_round,
            "prepared": tournament.prepared,
            "tables_count": len(tables),
            "players_active": active_players,
            "enough_tables_for_next_round": len(tables) >= max(1, active_players // 2),
        }

    @staticmethod
    def round_recommendation(players_count: int) -> int:
        """Default Swiss recommendation ceil(log2(N)), minimum 1."""

        if players_count <= 1:
            return 1
        return int(math.ceil(math.log2(players_count)))

    def _count_players(self) -> int:
        return len(self._player_repo.list_all())

    def _count_active_players(self) -> int:
        from domain.models import PlayerStatus

        return sum(1 for player in self._player_repo.list_all() if player.status == PlayerStatus.ACTIVE)
