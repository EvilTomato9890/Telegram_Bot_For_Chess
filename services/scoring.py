"""Scoring and standings service."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace

from domain.models import Game
from repositories import GameRepository, PlayerRepository, RoundRepository

_VALID_RESULTS = {"1-0", "0-1", "0.5-0.5", "bye", "forfeit"}


@dataclass(frozen=True, slots=True)
class StandingEntry:
    """Single player row in tournament standings."""

    position: int
    player_id: int
    telegram_user_id: int
    display_name: str
    score: float
    buchholz: float
    median_buchholz: float
    sonneborn_berger: float


@dataclass(frozen=True, slots=True)
class StandingsView:
    """Top standings payload including current player position."""

    top: tuple[StandingEntry, ...]
    player_position: int | None


class ScoringService:
    """Manage game results, score updates and standings."""

    def __init__(
        self,
        player_repository: PlayerRepository,
        round_repository: RoundRepository,
        game_repository: GameRepository,
    ) -> None:
        self._player_repository = player_repository
        self._round_repository = round_repository
        self._game_repository = game_repository

    def validate_result(self, result: str) -> str:
        if result not in _VALID_RESULTS:
            raise ValueError("invalid result token")
        return result

    def submit_result(self, game_id: int, result: str) -> Game:
        normalized_result = self.validate_result(result)
        game = self._game_repository.get(game_id)
        if game is None:
            raise ValueError("game not found")
        updated = replace(game, result=normalized_result)
        return self._game_repository.update(updated)

    def build_standings(self, tournament_id: int, include_sonneborn_berger: bool = True) -> tuple[StandingEntry, ...]:
        players = self._player_repository.list_by_tournament(tournament_id)
        rounds = self._round_repository.list_by_tournament(tournament_id)
        games = [game for round_ in rounds for game in self._game_repository.list_by_round(round_.id or 0)]

        player_scores: dict[int, float] = {player.id or 0: 0.0 for player in players}
        opponents: dict[int, list[int]] = defaultdict(list)
        results_by_player: dict[int, list[tuple[float, int]]] = defaultdict(list)

        for game in games:
            if game.result is None:
                continue
            white_points, black_points = self._result_points(game.result)
            player_scores[game.white_player_id] = player_scores.get(game.white_player_id, 0.0) + white_points

            if game.white_player_id == game.black_player_id:
                continue

            player_scores[game.black_player_id] = player_scores.get(game.black_player_id, 0.0) + black_points

            opponents[game.white_player_id].append(game.black_player_id)
            opponents[game.black_player_id].append(game.white_player_id)

            results_by_player[game.white_player_id].append((white_points, game.black_player_id))
            results_by_player[game.black_player_id].append((black_points, game.white_player_id))

        rows: list[StandingEntry] = []
        for player in players:
            player_id = player.id or 0
            player_score = player_scores.get(player_id, 0.0)
            opponent_scores = [player_scores.get(opponent_id, 0.0) for opponent_id in opponents.get(player_id, [])]
            buchholz = sum(opponent_scores)
            if len(opponent_scores) > 2:
                ordered_scores = sorted(opponent_scores)
                median_buchholz = sum(ordered_scores[1:-1])
            else:
                median_buchholz = buchholz
            sonneborn_berger = sum(
                points * player_scores.get(opponent_id, 0.0)
                for points, opponent_id in results_by_player.get(player_id, [])
            )
            persisted = replace(
                player,
                score=player_score,
                buchholz=buchholz,
                median_buchholz=median_buchholz,
                sonneborn_berger=sonneborn_berger,
            )
            self._player_repository.update(persisted)
            rows.append(
                StandingEntry(
                    position=0,
                    player_id=player_id,
                    telegram_user_id=player.telegram_user_id,
                    display_name=player.display_name,
                    score=player_score,
                    buchholz=buchholz,
                    median_buchholz=median_buchholz,
                    sonneborn_berger=sonneborn_berger,
                )
            )

        standings = sorted(
            rows,
            key=lambda row: (
                -row.score,
                -row.buchholz,
                -row.median_buchholz,
                -row.sonneborn_berger if include_sonneborn_berger else 0.0,
                row.display_name,
                row.player_id,
            ),
        )
        return tuple(replace(row, position=index) for index, row in enumerate(standings, start=1))

    def get_my_score(self, tournament_id: int, telegram_user_id: int) -> StandingEntry:
        standings = self.build_standings(tournament_id=tournament_id)
        for row in standings:
            if row.telegram_user_id == telegram_user_id:
                return row
        raise ValueError("player is not registered in this tournament")

    def get_standings(self, tournament_id: int, top_n: int, telegram_user_id: int | None = None) -> StandingsView:
        if top_n <= 0:
            raise ValueError("top_n must be positive")
        standings = self.build_standings(tournament_id=tournament_id)
        position: int | None = None
        if telegram_user_id is not None:
            for row in standings:
                if row.telegram_user_id == telegram_user_id:
                    position = row.position
                    break
        return StandingsView(top=standings[:top_n], player_position=position)

    @staticmethod
    def _result_points(result: str) -> tuple[float, float]:
        if result == "1-0":
            return (1.0, 0.0)
        if result == "0-1":
            return (0.0, 1.0)
        if result == "0.5-0.5":
            return (0.5, 0.5)
        if result == "bye":
            return (1.0, 0.0)
        if result == "forfeit":
            return (1.0, 0.0)
        raise ValueError("invalid result token")


__all__ = ["ScoringService", "StandingEntry", "StandingsView"]
