"""Standings and tie-break calculations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from domain.exceptions import DomainError
from domain.models import GameResult, Player
from repositories import GameRepository, PlayerRepository, RoundRepository


RESULT_ALIASES: dict[str, GameResult] = {
    "white": GameResult.WHITE_WIN,
    "белые": GameResult.WHITE_WIN,
    "1-0": GameResult.WHITE_WIN,
    "black": GameResult.BLACK_WIN,
    "черные": GameResult.BLACK_WIN,
    "чёрные": GameResult.BLACK_WIN,
    "0-1": GameResult.BLACK_WIN,
    "draw": GameResult.DRAW,
    "ничья": GameResult.DRAW,
    "0.5-0.5": GameResult.DRAW,
    "bye": GameResult.BYE,
    "forfeit": GameResult.FORFEIT,
}


@dataclass(frozen=True, slots=True)
class StandingRow:
    """One final standings row."""

    position: int
    player_id: int
    telegram_id: int
    full_name: str
    rating: int
    score: float
    buchholz: float
    median_buchholz: float
    sonneborn_berger: float


class ScoringService:
    """Compute and persist scores + tie-break values."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        round_repo: RoundRepository,
        game_repo: GameRepository,
    ) -> None:
        self._player_repo = player_repo
        self._round_repo = round_repo
        self._game_repo = game_repo

    def parse_result_token(self, raw: str) -> GameResult:
        """Normalize user input token to canonical GameResult."""

        normalized = raw.strip().lower()
        result = RESULT_ALIASES.get(normalized)
        if result is None:
            raise DomainError("Некорректный результат. Используйте White/Black/Draw.")
        return result

    def result_points(self, result: GameResult) -> tuple[float, float]:
        """Map canonical game result to white/black points."""

        if result == GameResult.WHITE_WIN:
            return (1.0, 0.0)
        if result == GameResult.BLACK_WIN:
            return (0.0, 1.0)
        if result == GameResult.DRAW:
            return (0.5, 0.5)
        if result == GameResult.BYE:
            return (1.0, 0.0)
        if result == GameResult.FORFEIT:
            return (1.0, 0.0)
        raise DomainError("unknown result")

    def recalculate(self) -> tuple[StandingRow, ...]:
        """Recompute standings and write values back to players table."""

        players = self._player_repo.list_all()
        rounds = self._round_repo.list_all()
        round_ids = [round_.id for round_ in rounds if round_.id is not None]
        games = [
            game
            for round_id in round_ids
            for game in self._game_repo.list_by_round(round_id)
            if game.result is not None
        ]

        player_scores: dict[int, float] = {player.id or 0: 0.0 for player in players}
        opponents: dict[int, list[int]] = defaultdict(list)
        sb_terms: dict[int, list[tuple[float, int]]] = defaultdict(list)

        for game in games:
            if game.result is None:
                continue
            white_points, black_points = self.result_points(game.result)
            player_scores[game.white_player_id] = player_scores.get(game.white_player_id, 0.0) + white_points
            if game.is_bye:
                continue
            player_scores[game.black_player_id] = player_scores.get(game.black_player_id, 0.0) + black_points
            opponents[game.white_player_id].append(game.black_player_id)
            opponents[game.black_player_id].append(game.white_player_id)
            sb_terms[game.white_player_id].append((white_points, game.black_player_id))
            sb_terms[game.black_player_id].append((black_points, game.white_player_id))

        rows: list[StandingRow] = []
        for player in players:
            player_id = player.id or 0
            opponent_scores = [player_scores.get(opp, 0.0) for opp in opponents.get(player_id, [])]
            buchholz = sum(opponent_scores)
            if len(opponent_scores) >= 3:
                ordered = sorted(opponent_scores)
                median_buchholz = sum(ordered[1:-1])
            else:
                median_buchholz = buchholz
            sonneborn_berger = sum(
                result_points * player_scores.get(opp_id, 0.0)
                for result_points, opp_id in sb_terms.get(player_id, [])
            )
            updated = Player(
                id=player.id,
                telegram_id=player.telegram_id,
                username=player.username,
                full_name=player.full_name,
                rating=player.rating,
                status=player.status,
                score=player_scores.get(player_id, 0.0),
                buchholz=buchholz,
                median_buchholz=median_buchholz,
                sonneborn_berger=sonneborn_berger,
                had_bye=player.had_bye,
                current_board=player.current_board,
                seat_hint=player.seat_hint,
                created_at=player.created_at,
            )
            self._player_repo.update(updated)
            rows.append(
                StandingRow(
                    position=0,
                    player_id=player_id,
                    telegram_id=player.telegram_id,
                    full_name=player.full_name,
                    rating=player.rating,
                    score=updated.score,
                    buchholz=buchholz,
                    median_buchholz=median_buchholz,
                    sonneborn_berger=sonneborn_berger,
                )
            )

        sorted_rows = sorted(
            rows,
            key=lambda row: (
                -row.score,
                -row.buchholz,
                -row.median_buchholz,
                -row.sonneborn_berger,
                -row.rating,
                row.full_name.lower(),
                row.player_id,
            ),
        )
        return tuple(
            StandingRow(
                position=index,
                player_id=row.player_id,
                telegram_id=row.telegram_id,
                full_name=row.full_name,
                rating=row.rating,
                score=row.score,
                buchholz=row.buchholz,
                median_buchholz=row.median_buchholz,
                sonneborn_berger=row.sonneborn_berger,
            )
            for index, row in enumerate(sorted_rows, start=1)
        )

    def standings(self, top_n: int) -> tuple[StandingRow, ...]:
        """Return top-N standings rows."""

        if top_n <= 0:
            raise DomainError("top_n должен быть положительным.")
        return self.recalculate()[:top_n]

    def my_score(self, telegram_id: int) -> StandingRow:
        """Return one player's standings row."""

        for row in self.recalculate():
            if row.telegram_id == telegram_id:
                return row
        raise DomainError("Игрок не зарегистрирован.")

