"""Player reporting and arbiter approval flow."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.dto import ApproveOutcome, ReportOutcome
from domain.exceptions import DomainError
from domain.models import Game, RoundStatus, TournamentStatus
from repositories import GameReportRepository, GameRepository, PlayerRepository, RoundRepository, TournamentRepository

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
    ) -> None:
        self._player_repo = player_repo
        self._round_repo = round_repo
        self._game_repo = game_repo
        self._report_repo = report_repo
        self._tournament_repo = tournament_repo
        self._scoring_service = scoring_service

    def ensure_reportable_game(self, telegram_id: int) -> None:
        """Validate that player currently has an active game for /report."""

        player = self._player_repo.get_by_telegram_id(telegram_id)
        if player is None or player.id is None:
            raise DomainError("Игрок не зарегистрирован.")
        self._resolve_game_for_player(player.id)

    def submit_player_report(self, telegram_id: int, raw_result: str) -> ReportOutcome:
        """Store player report and finalize game on agreement."""

        player = self._player_repo.get_by_telegram_id(telegram_id)
        if player is None or player.id is None:
            raise DomainError("Игрок не зарегистрирован.")
        result = self._scoring_service.parse_result_token(raw_result)
        game = self._resolve_game_for_player(player.id)
        if game.result is not None:
            raise DomainError("Результат уже зафиксирован. Обратитесь к арбитру.")
        if player.id not in {game.white_player_id, game.black_player_id}:
            raise DomainError("Нельзя репортить результат чужой партии.")

        game_id = game.id or 0
        self._report_repo.upsert(game_id, player.id, result)
        white_tg, black_tg = self._resolve_player_telegram_ids(game)

        opponent_id = game.black_player_id if game.white_player_id == player.id else game.white_player_id
        reports = self._report_repo.list_by_game(game_id)
        own = next((report for report in reports if report.reporter_player_id == player.id), None)
        opp = next((report for report in reports if report.reporter_player_id == opponent_id), None)
        if own is None:
            raise DomainError("Не удалось сохранить отчет.")
        if opp is None:
            return ReportOutcome(
                game_id=game_id,
                status="pending",
                message=f"Ваш результат {own.reported_result.value} сохранен, ожидаем отчет соперника.",
                confirmed_result=own.reported_result.value,
                white_telegram_id=white_tg,
                black_telegram_id=black_tg,
            )

        if opp.reported_result == own.reported_result:
            game.result = own.reported_result
            game.result_source = "players"
            game.updated_at = datetime.now(UTC)
            self._game_repo.update(game)
            self._report_repo.delete_by_game(game_id)
            self._scoring_service.recalculate()
            round_closed, round_number = self._close_round_if_needed(game.round_id)
            next_round_hint = self._next_round_hint(round_number)
            return ReportOutcome(
                game_id=game_id,
                status="agreed",
                message=f"Результат подтвержден: {own.reported_result.value}.",
                confirmed_result=own.reported_result.value,
                white_telegram_id=white_tg,
                black_telegram_id=black_tg,
                round_closed=round_closed,
                round_number=round_number,
                next_round_hint=next_round_hint,
            )

        return ReportOutcome(
            game_id=game_id,
            status="conflict",
            message=(
                f"Конфликт: ваш результат {own.reported_result.value}, "
                f"у соперника {opp.reported_result.value}."
            ),
            confirmed_result=own.reported_result.value,
            white_telegram_id=white_tg,
            black_telegram_id=black_tg,
        )

    def approve_result(self, game_id: int, raw_result: str) -> ApproveOutcome:
        """Arbitrator/admin overrides game result for current round only."""

        game = self._game_repo.get_by_id(game_id)
        if game is None:
            raise DomainError("Игра не найдена.")
        tournament = self._tournament_repo.get()
        if tournament is None or tournament.status != TournamentStatus.ONGOING:
            raise DomainError("Подтверждение результата доступно только во время турнира.")
        round_ = self._round_repo.get_by_id(game.round_id)
        if round_ is None:
            raise DomainError("Тур игры не найден.")
        if round_.number != tournament.current_round:
            raise DomainError("Изменять результат можно только в текущем туре до старта следующего.")

        result = self._scoring_service.parse_result_token(raw_result)
        game.result = result
        game.result_source = "arbiter"
        game.updated_at = datetime.now(UTC)
        self._game_repo.update(game)
        self._report_repo.delete_by_game(game_id)
        self._scoring_service.recalculate()

        round_closed, round_number = self._close_round_if_needed(game.round_id)
        white_tg, black_tg = self._resolve_player_telegram_ids(game)
        return ApproveOutcome(
            game_id=game_id,
            confirmed_result=result.value,
            message=f"Результат игры {game_id} подтвержден: {result.value}.",
            white_telegram_id=white_tg,
            black_telegram_id=black_tg,
            round_closed=round_closed,
            round_number=round_number,
            next_round_hint=self._next_round_hint(round_number),
        )

    def _resolve_game_for_player(self, player_id: int) -> Game:
        tournament = self._tournament_repo.get()
        if tournament is None:
            raise DomainError("Турнир не создан.")
        if tournament.status != TournamentStatus.ONGOING or tournament.current_round <= 0:
            raise DomainError("Нет активной партии для /report.")
        current_round = self._round_repo.get_by_number(tournament.current_round)
        if current_round is None or current_round.id is None or current_round.status != RoundStatus.ONGOING:
            raise DomainError("Нет активной партии для /report.")

        games = self._game_repo.list_by_player(player_id)
        for game in games:
            if game.round_id == current_round.id and game.result is None and not game.is_bye:
                return game
        raise DomainError("Нет активной партии для /report.")

    def _resolve_player_telegram_ids(self, game: Game) -> tuple[int | None, int | None]:
        white_player = self._player_repo.get_by_id(game.white_player_id)
        black_player = self._player_repo.get_by_id(game.black_player_id)
        return (
            white_player.telegram_id if white_player is not None else None,
            black_player.telegram_id if black_player is not None else None,
        )

    def _close_round_if_needed(self, round_id: int) -> tuple[bool, int | None]:
        round_ = self._round_repo.get_by_id(round_id)
        if round_ is None:
            return (False, None)
        games = self._game_repo.list_by_round(round_id)
        if games and all(game.result is not None for game in games):
            if round_.status != RoundStatus.CLOSED:
                round_.status = RoundStatus.CLOSED
                round_.closed_at = datetime.now(UTC)
                self._round_repo.update(round_)
            return (True, round_.number)
        return (False, round_.number)

    def _next_round_hint(self, current_round_number: int | None) -> str:
        if current_round_number is None:
            return "Время следующего тура пока не назначено."
        next_round = self._round_repo.get_by_number(current_round_number + 1)
        if next_round is None:
            return "Время следующего тура пока не назначено."
        if next_round.starts_at is not None and next_round.window_end_at is not None:
            return (
                f"Следующий тур {next_round.number}: "
                f"{next_round.starts_at.isoformat()} - {next_round.window_end_at.isoformat()}."
            )
        if next_round.starts_at is not None:
            return f"Следующий тур {next_round.number}: начало {next_round.starts_at.isoformat()}."
        if next_round.window_end_at is not None:
            return f"Следующий тур {next_round.number}: дедлайн {next_round.window_end_at.isoformat()}."
        return "Время следующего тура пока не назначено."
