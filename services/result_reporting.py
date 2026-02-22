"""Player result reporting workflow with arbiter approval."""

from __future__ import annotations

from dataclasses import dataclass

from domain.models import Game
from repositories import GameRepository, RoundRepository

from .access_control import AccessControlService
from .scoring import ScoringService
from .contracts import NotificationService


@dataclass(frozen=True, slots=True)
class ReportResolution:
    """Outcome of a report submission."""

    game_id: int
    status: str
    message: str


class ResultReportingService:
    """Collect player reports and resolve game results on agreement."""

    def __init__(
        self,
        *,
        game_repository: GameRepository,
        round_repository: RoundRepository,
        scoring_service: ScoringService,
        notification_service: NotificationService,
        access_control_service: AccessControlService,
    ) -> None:
        self._game_repository = game_repository
        self._round_repository = round_repository
        self._scoring_service = scoring_service
        self._notification_service = notification_service
        self._access_control_service = access_control_service
        self._reports_by_game: dict[int, dict[int, str]] = {}

    def submit_report(self, player_id: int, result: str) -> ReportResolution:
        normalized_result = self._scoring_service.validate_result(result)
        game = self._resolve_current_or_last_game(player_id)

        game_id = self._require_game_id(game)
        reports = self._reports_by_game.setdefault(game_id, {})
        reports[player_id] = normalized_result

        opponent_id = self._opponent_id(game, player_id)
        opponent_report = reports.get(opponent_id)
        if opponent_report is None:
            return ReportResolution(
                game_id=game_id,
                status="pending",
                message="report saved; waiting for opponent report",
            )

        if opponent_report == normalized_result:
            self._scoring_service.submit_result(game_id, normalized_result)
            self._reports_by_game.pop(game_id, None)
            self._notification_service.notify(
                f"Game {game_id} result agreed by players: {normalized_result}."
            )
            self._notify_organizers_if_round_closed(game.round_id)
            return ReportResolution(
                game_id=game_id,
                status="agreed",
                message="reports matched, result applied",
            )

        self._notification_service.notify(
            "Players "
            f"{game.white_player_id} and {game.black_player_id} reported different results for game "
            f"{self._require_game_id(game)}. Please repeat /report or call an arbiter via /approve_result."
        )
        return ReportResolution(
            game_id=game_id,
            status="conflict",
            message="reports conflict; players have been notified",
        )

    def approve_result(self, arbiter_user_id: int, game_id: int, result: str) -> Game:
        if not self._access_control_service.has_any_role(arbiter_user_id, {"arbiter", "admin"}):
            raise ValueError("only arbiter/admin can approve results")
        normalized_result = self._scoring_service.validate_result(result)
        updated_game = self._scoring_service.submit_result(game_id, normalized_result)
        self._reports_by_game.pop(game_id, None)
        self._notification_service.notify(
            f"Arbiter {arbiter_user_id} approved result for game {game_id}: {normalized_result}."
        )
        self._notify_organizers_if_round_closed(updated_game.round_id)
        return updated_game

    def _resolve_current_or_last_game(self, player_id: int) -> Game:
        candidate_games = [
            game
            for game in self._game_repository.list_all()
            if game.white_player_id == player_id or game.black_player_id == player_id
        ]
        if not candidate_games:
            raise ValueError("player has no games")

        unresolved_games = [game for game in candidate_games if game.result is None]
        source = unresolved_games if unresolved_games else candidate_games
        return max(source, key=self._game_sort_key)

    def _game_sort_key(self, game: Game) -> tuple[int, int]:
        round_ = self._round_repository.get(game.round_id)
        round_number = round_.number if round_ is not None else -1
        return (round_number, self._require_game_id(game))

    def _opponent_id(self, game: Game, player_id: int) -> int:
        if game.white_player_id == player_id:
            return game.black_player_id
        if game.black_player_id == player_id:
            return game.white_player_id
        raise ValueError("player can report only own current/last game")

    @staticmethod
    def _require_game_id(game: Game) -> int:
        if game.id is None:
            raise ValueError("game.id is required")
        return game.id

    def _notify_organizers_if_round_closed(self, round_id: int) -> None:
        games = self._game_repository.list_by_round(round_id)
        if games and all(game.result is not None for game in games):
            self._notification_service.notify(
                f"[ORGANIZERS] Round {round_id} is fully closed (all game results are set)."
            )
