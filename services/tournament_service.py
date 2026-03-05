"""Tournament lifecycle management."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, datetime

from domain.exceptions import DomainError
from domain.models import PlayerStatus, RoundStatus, Tournament, TournamentStatus
from infra.db import Database
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
        database: Database,
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
        self._database = database
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

    def create_tournament(self) -> Tournament:
        """Reset tournament into draft and clear all runtime data."""

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

        with self._database.transaction() as conn:
            self._report_repo.clear_all(conn)
            self._game_repo.clear_all(conn)
            self._round_repo.clear_all(conn)
            self._ticket_repo.clear_all(conn)
            self._player_repo.clear_all(conn)
            self._table_repo.clear_all(conn)
            conn.execute("DELETE FROM role_grants")
            conn.execute(
                """
                DELETE FROM sqlite_sequence
                WHERE name IN ('players', 'rounds', 'tables', 'games', 'game_reports', 'tickets', 'role_grants')
                """
            )

        return stored

    def validate_open_registration(self) -> None:
        """Validate preconditions for opening registration without mutating state."""

        tournament = self.ensure_tournament()
        if tournament.status != TournamentStatus.DRAFT:
            raise DomainError("Открыть регистрацию можно только из статуса draft.")
        player_count = self._count_active_players()
        max_capacity = len(self._table_repo.list_all()) * 2
        if player_count > max_capacity:
            raise DomainError("Игроков уже больше чем 2 * число столов.")

    def open_registration(self) -> Tournament:
        """Move tournament from draft to registration."""

        self.validate_open_registration()
        return self._tournament_repo.update_status(TournamentStatus.REGISTRATION, prepared=False)

    def validate_set_round_number(self, rounds: int, *, confirm: bool) -> int:
        """Validate round-number update preconditions and return recommendation."""

        if rounds <= 0:
            raise DomainError("Число туров должно быть положительным.")
        tournament = self.ensure_tournament()
        if tournament.status not in {TournamentStatus.DRAFT, TournamentStatus.REGISTRATION}:
            raise DomainError("Число туров можно менять только до старта турнира.")
        recommendation = self.round_recommendation(self._count_active_players())
        if rounds != recommendation and not confirm:
            raise DomainError(
                f"Рекомендованное число туров: {recommendation}. "
                "Повторите команду с confirm для подтверждения."
            )
        return recommendation

    def set_round_number(self, rounds: int, *, confirm: bool) -> tuple[Tournament, int]:
        """Set number of rounds with recommendation check."""

        recommendation = self.validate_set_round_number(rounds, confirm=confirm)
        tournament = self.ensure_tournament()
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
            raise DomainError("Текст правил не может быть пустым.")
        tournament = self.ensure_tournament()
        return self._tournament_repo.update_status(
            tournament.status,
            number_of_rounds=tournament.number_of_rounds,
            prepared=tournament.prepared,
            current_round=tournament.current_round,
            rules_text=text.strip(),
            pending_pairing_payload=tournament.pending_pairing_payload,
        )

    def validate_prepare_readiness(self) -> list[str]:
        """Validate all hard preconditions required by /prepare_tournament."""

        problems: list[str] = []
        tournament = self.ensure_tournament()
        if tournament.status != TournamentStatus.REGISTRATION:
            problems.append("статус турнира должен быть registration")
        if tournament.number_of_rounds <= 0:
            problems.append("не задано число туров (/set_round_number)")

        tables_count = len(self._table_repo.list_all())
        active_players = self._count_active_players()

        if tables_count < 1:
            problems.append("не добавлено ни одного стола")
        if active_players < 2:
            problems.append("нужно минимум 2 активных участника")
        if tables_count > 0 and active_players > tables_count * 2:
            problems.append(
                f"активных участников {active_players}, но вместимость текущих столов только {tables_count * 2}"
            )
        required_tables = active_players // 2
        if tables_count < required_tables:
            problems.append(f"недостаточно столов: нужно минимум {required_tables}, доступно {tables_count}")
        return problems

    def prepare_tournament(self) -> Tournament:
        """Lock registration and mark tournament as prepared."""

        problems = self.validate_prepare_readiness()
        if problems:
            raise DomainError("Подготовка невозможна:\n- " + "\n- ".join(problems))

        tournament = self.ensure_tournament()
        return self._tournament_repo.update_status(
            TournamentStatus.REGISTRATION,
            prepared=True,
            number_of_rounds=tournament.number_of_rounds,
            current_round=tournament.current_round,
            rules_text=tournament.rules_text,
            pending_pairing_payload=tournament.pending_pairing_payload,
        )

    def validate_start_tournament(self) -> None:
        """Validate preconditions for starting tournament without mutating state."""

        tournament = self.ensure_tournament()
        if tournament.status != TournamentStatus.REGISTRATION:
            raise DomainError("Турнир можно стартовать только из registration.")
        if not tournament.prepared:
            raise DomainError("Сначала выполните /prepare_tournament.")
        if tournament.number_of_rounds <= 0:
            raise DomainError("Сначала задайте число туров через /set_round_number.")
        if self._count_active_players() < 2:
            raise DomainError("Для старта нужно минимум 2 активных игрока.")

    def start_tournament(self) -> Tournament:
        """Move tournament to ongoing status."""

        self.validate_start_tournament()
        tournament = self.ensure_tournament()
        return self._tournament_repo.update_status(
            TournamentStatus.ONGOING,
            prepared=True,
            number_of_rounds=tournament.number_of_rounds,
            current_round=tournament.current_round,
            rules_text=tournament.rules_text,
            pending_pairing_payload=tournament.pending_pairing_payload,
        )

    def end_current_round(self) -> None:
        """Close current round when all its games have results."""

        current = self._round_repo.get_current()
        if current is None:
            tournament = self.ensure_tournament()
            if tournament.current_round <= 0:
                raise DomainError("Нет активного тура.")
            closed_round = self._round_repo.get_by_number(tournament.current_round)
            if closed_round is not None and closed_round.status == RoundStatus.CLOSED:
                return
            current = closed_round
        if current is None:
            raise DomainError("Нет активного тура.")
        if current.status == RoundStatus.CLOSED:
            return
        games = self._game_repo.list_by_round(current.id or 0)
        if not games or any(game.result is None for game in games):
            raise DomainError("Нельзя закрыть тур: не все результаты зафиксированы.")
        current.status = RoundStatus.CLOSED
        current.closed_at = datetime.now(UTC)
        self._round_repo.update(current)

    def validate_finish_tournament(self) -> None:
        """Validate preconditions for finishing tournament without mutating state."""

        tournament = self.ensure_tournament()
        if tournament.status != TournamentStatus.ONGOING:
            raise DomainError("Завершение доступно только для ongoing турнира.")
        current = self._round_repo.get_current()
        if current is not None and current.status != RoundStatus.CLOSED:
            raise DomainError("Сначала закройте текущий тур.")

    def finish_tournament(self) -> Tournament:
        """Mark tournament as finished."""

        self.validate_finish_tournament()
        tournament = self.ensure_tournament()
        return self._tournament_repo.update_status(
            TournamentStatus.FINISHED,
            prepared=tournament.prepared,
            number_of_rounds=tournament.number_of_rounds,
            current_round=tournament.current_round,
            rules_text=tournament.rules_text,
            pending_pairing_payload=None,
        )

    def force_finish_tournament(self) -> Tournament:
        """Force tournament finish without procedural validations."""

        tournament = self.ensure_tournament()
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
        required_tables = active_players // 2 if active_players >= 2 else 0
        return {
            "status": tournament.status.value,
            "rounds_total": tournament.number_of_rounds,
            "round_current": tournament.current_round,
            "prepared": tournament.prepared,
            "tables_count": len(tables),
            "players_active": active_players,
            "players_disqualified": self._count_disqualified_players(),
            "enough_tables_for_next_round": len(tables) >= required_tables,
        }

    def invalidate_pending_pairings(self) -> bool:
        """Drop prepared next-round payload and clear preview placements."""

        tournament = self.ensure_tournament()
        if tournament.pending_pairing_payload is None:
            return False
        self._tournament_repo.update_status(
            tournament.status,
            prepared=tournament.prepared,
            number_of_rounds=tournament.number_of_rounds,
            current_round=tournament.current_round,
            rules_text=tournament.rules_text,
            pending_pairing_payload=None,
        )
        for player in self._player_repo.list_all():
            if player.current_board is None and not (player.seat_hint or "").strip():
                continue
            player.current_board = None
            player.seat_hint = None
            self._player_repo.update(player)
        return True

    @staticmethod
    def round_recommendation(players_count: int) -> int:
        """Default Swiss recommendation ceil(log2(N)), minimum 1."""

        if players_count <= 1:
            return 1
        return int(math.ceil(math.log2(players_count)))

    def _count_active_players(self) -> int:
        return sum(1 for player in self._player_repo.list_all() if player.status == PlayerStatus.ACTIVE)

    def _count_disqualified_players(self) -> int:
        return sum(1 for player in self._player_repo.list_all() if player.status == PlayerStatus.DISQUALIFIED)
