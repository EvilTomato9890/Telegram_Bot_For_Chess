"""Player reporting and arbiter approval flow."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.dto import ReportOutcome
from domain.models import Game, RoundStatus, TournamentStatus
from repositories import GameReportRepository, GameRepository, PlayerRepository, RoundRepository, TournamentRepository

from .notification_service import NotificationService
from .scoring_service import ScoringService


class ResultService:
    """Apply reports, resolve conflicts and finalize game results."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        round_repo: RoundRepository,
        game_repo: GameRepository,
        report_repo: GameReportRepository,
        tournament_repo: TournamentRepository,
        scoring_service: ScoringService,
        notification_service: NotificationService,
    ) -> None:
        self._player_repo = player_repo
        self._round_repo = round_repo
        self._game_repo = game_repo
        self._report_repo = report_repo
        self._tournament_repo = tournament_repo
        self._scoring_service = scoring_service
        self._notification_service = notification_service

    def ensure_reportable_game(self, telegram_id: int) -> None:
        """Validate that player currently has an active game for /report."""

        player = self._player_repo.get_by_telegram_id(telegram_id)
        if player is None or player.id is None:
            raise ValueError("Игрок не зарегистрирован.")
        self._resolve_game_for_player(player.id)

    def submit_player_report(self, telegram_id: int, raw_result: str) -> ReportOutcome:
        """Store player report and finalize game on agreement."""

        player = self._player_repo.get_by_telegram_id(telegram_id)
        if player is None or player.id is None:
            raise ValueError("Игрок не зарегистрирован.")
        result = self._scoring_service.parse_result_token(raw_result)
        game = self._resolve_game_for_player(player.id)
        if game.result is not None:
            raise ValueError("Результат уже зафиксирован. Обратитесь к арбитру.")
        if player.id not in {game.white_player_id, game.black_player_id}:
            raise ValueError("Нельзя репортить результат чужой партии.")

        game_id = game.id or 0
        self._report_repo.upsert(game_id, player.id, result)

        opponent_id = game.black_player_id if game.white_player_id == player.id else game.white_player_id
        reports = self._report_repo.list_by_game(game_id)
        own = next((r for r in reports if r.reporter_player_id == player.id), None)
        opp = next((r for r in reports if r.reporter_player_id == opponent_id), None)
        if own is None:
            raise ValueError("Не удалось сохранить отчет.")
        if opp is None:
            return ReportOutcome(
                game_id=game_id,
                status="pending",
                message=f"Ваш результат {own.reported_result.value} сохранен, ожидаем отчет соперника.",
            )

        if opp.reported_result == own.reported_result:
            game.result = own.reported_result
            game.result_source = "players"
            game.updated_at = datetime.now(UTC)
            self._game_repo.update(game)
            self._report_repo.delete_by_game(game_id)
            self._scoring_service.recalculate()
            self._notification_service.notify(
                f"Игра {game_id}: оба игрока подтвердили результат {own.reported_result.value}."
            )
            self._notify_round_closed_if_needed(game.round_id)
            return ReportOutcome(
                game_id=game_id,
                status="agreed",
                message=f"Результат подтвержден: {own.reported_result.value}.",
            )

        self._notification_service.notify(
            f"Конфликт репортов в игре {game_id}. Повторите /report или вызовите арбитра."
        )
        return ReportOutcome(
            game_id=game_id,
            status="conflict",
            message=(
                f"Конфликт: ваш результат {own.reported_result.value}, "
                f"у соперника {opp.reported_result.value}."
            ),
        )

    def approve_result(self, game_id: int, raw_result: str) -> None:
        """Arbitrator/admin overrides game result for current round only."""

        game = self._game_repo.get_by_id(game_id)
        if game is None:
            raise ValueError("Игра не найдена.")
        tournament = self._tournament_repo.get()
        if tournament is None or tournament.status != TournamentStatus.ONGOING:
            raise ValueError("Подтверждение результата доступно только во время турнира.")
        round_ = self._round_repo.get_by_id(game.round_id)
        if round_ is None:
            raise ValueError("Тур игры не найден.")
        if round_.number != tournament.current_round:
            raise ValueError("Изменять результат можно только в текущем туре до старта следующего.")

        result = self._scoring_service.parse_result_token(raw_result)
        game.result = result
        game.result_source = "arbiter"
        game.updated_at = datetime.now(UTC)
        self._game_repo.update(game)
        self._report_repo.delete_by_game(game_id)
        self._scoring_service.recalculate()
        self._notification_service.notify(f"Арбитр подтвердил результат игры {game_id}: {result.value}.")
        self._notify_round_closed_if_needed(game.round_id)

    def _resolve_game_for_player(self, player_id: int) -> Game:
        tournament = self._tournament_repo.get()
        if tournament is None:
            raise ValueError("Турнир не создан.")
        if tournament.status != TournamentStatus.ONGOING or tournament.current_round <= 0:
            raise ValueError("Нет активной партии для /report.")
        current_round = self._round_repo.get_by_number(tournament.current_round)
        if current_round is None or current_round.id is None or current_round.status != RoundStatus.ONGOING:
            raise ValueError("Нет активной партии для /report.")

        games = self._game_repo.list_by_player(player_id)
        for game in games:
            if game.round_id == current_round.id and game.result is None and not game.is_bye:
                return game
        raise ValueError("Нет активной партии для /report.")

    def _notify_round_closed_if_needed(self, round_id: int) -> None:
        round_ = self._round_repo.get_by_id(round_id)
        if round_ is None:
            return
        games = self._game_repo.list_by_round(round_id)
        if games and all(game.result is not None for game in games):
            if round_.status != RoundStatus.CLOSED:
                round_.status = RoundStatus.CLOSED
                round_.closed_at = datetime.now(UTC)
                self._round_repo.update(round_)
            self._notification_service.notify(
                f"[ORGANIZERS] Тур {round_.number} полностью закрыт, можно готовить следующий."
            )

