"""Swiss pairing orchestration service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from domain.dto import PairingOutcome
from domain.models import Game, GameResult, PlayerStatus, Round, RoundStatus, Tournament, TournamentStatus
from repositories import GameRepository, PlayerRepository, RoundRepository, TableRepository, TournamentRepository

from .pairing_engine import PairingPlayer, TableSlot, generate_pairings
from .scoring_service import ScoringService


class PairingService:
    """Generate rounds and persist pairings."""

    def __init__(
        self,
        tournament_repo: TournamentRepository,
        player_repo: PlayerRepository,
        round_repo: RoundRepository,
        game_repo: GameRepository,
        table_repo: TableRepository,
        scoring_service: ScoringService,
    ) -> None:
        self._tournament_repo = tournament_repo
        self._player_repo = player_repo
        self._round_repo = round_repo
        self._game_repo = game_repo
        self._table_repo = table_repo
        self._scoring_service = scoring_service

    def generate_next_round(self, tournament_id: int, actor_id: int, force: bool = False) -> PairingOutcome:
        """Generate next round pairings with optional forced repeats."""

        del tournament_id, actor_id  # Single-tournament mode.
        tournament = self._require_ongoing_tournament()
        self._validate_can_generate(tournament)

        if force and tournament.pending_pairing_payload:
            return self._persist_pending_round(tournament)

        active_players = [player for player in self._player_repo.list_all() if player.status == PlayerStatus.ACTIVE]
        if len(active_players) < 2:
            raise ValueError("Недостаточно активных игроков для генерации тура.")

        tables = self._table_repo.list_all()
        slots = [TableSlot(location=table.location, place=table.place_hint or "без уточнения") for table in tables]
        history = self._build_history(active_players)
        engine_result = generate_pairings(history, slots)

        if engine_result.confirmation_request is not None and not force:
            payload = {
                "reason": engine_result.confirmation_request.reason,
                "games": [
                    {
                        "table_number": game.table_number,
                        "location": game.location,
                        "white_player_id": game.white_player_id,
                        "black_player_id": game.black_player_id,
                    }
                    for game in engine_result.games
                ],
                "bye_player_id": engine_result.bye.player_id if engine_result.bye else None,
            }
            self._tournament_repo.update_status(
                tournament.status,
                prepared=tournament.prepared,
                number_of_rounds=tournament.number_of_rounds,
                current_round=tournament.current_round,
                rules_text=tournament.rules_text,
                pending_pairing_payload=json.dumps(payload, ensure_ascii=False),
            )
            return PairingOutcome(
                round_number=tournament.current_round + 1,
                games=tuple(),
                bye_player_id=payload["bye_player_id"],
                needs_confirmation=True,
                confirmation_reason=payload["reason"],
            )

        pairing_data = [
            {
                "table_number": game.table_number,
                "location": game.location,
                "white_player_id": game.white_player_id,
                "black_player_id": game.black_player_id,
            }
            for game in engine_result.games
        ]
        return self._persist_generated_round(
            tournament=tournament,
            pairing_data=pairing_data,
            bye_player_id=engine_result.bye.player_id if engine_result.bye else None,
        )

    def confirm_next_round(self, tournament_id: int, actor_id: int) -> PairingOutcome:
        """Force next round generation using the previously stored pending payload."""

        del tournament_id, actor_id
        tournament = self._require_ongoing_tournament()
        if not tournament.pending_pairing_payload:
            raise ValueError("Нет ожидающего подтверждения генерации.")
        self._validate_can_generate(tournament)
        return self._persist_pending_round(tournament)

    def _validate_can_generate(self, tournament: Tournament) -> None:
        if tournament.current_round > 0:
            current_round = self._round_repo.get_by_number(tournament.current_round)
            if current_round is not None and current_round.status != RoundStatus.CLOSED:
                raise ValueError("Сначала закройте текущий тур перед генерацией следующего.")
        if tournament.number_of_rounds and tournament.current_round >= tournament.number_of_rounds:
            raise ValueError("Достигнуто заданное число туров.")

    def _require_ongoing_tournament(self) -> Tournament:
        tournament = self._tournament_repo.get()
        if tournament is None:
            raise ValueError("Турнир не создан.")
        if tournament.status != TournamentStatus.ONGOING:
            raise ValueError("Генерация пар доступна только в ongoing.")
        return tournament

    def _build_history(self, active_players: list[Any]) -> list[PairingPlayer]:
        games = self._game_repo.list_all()
        opponents: dict[int, set[int]] = {player.id or 0: set() for player in active_players}
        colors: dict[int, list[str]] = {player.id or 0: [] for player in active_players}
        had_bye: dict[int, bool] = {player.id or 0: player.had_bye for player in active_players}
        for game in games:
            if game.is_bye:
                had_bye[game.white_player_id] = True
                continue
            opponents.setdefault(game.white_player_id, set()).add(game.black_player_id)
            opponents.setdefault(game.black_player_id, set()).add(game.white_player_id)
            colors.setdefault(game.white_player_id, []).append("W")
            colors.setdefault(game.black_player_id, []).append("B")
        return [
            PairingPlayer(
                player_id=player.id or 0,
                display_name=player.full_name,
                score=player.score,
                opponents=frozenset(opponents.get(player.id or 0, set())),
                color_history=tuple(colors.get(player.id or 0, [])),
                had_bye=had_bye.get(player.id or 0, False),
            )
            for player in active_players
        ]

    def _persist_pending_round(self, tournament: Tournament) -> PairingOutcome:
        payload = json.loads(tournament.pending_pairing_payload or "{}")
        pairing_data = payload.get("games", [])
        return self._persist_generated_round(
            tournament=tournament,
            pairing_data=pairing_data,
            bye_player_id=payload.get("bye_player_id"),
        )

    def _persist_generated_round(
        self,
        *,
        tournament: Tournament,
        pairing_data: list[dict[str, Any]],
        bye_player_id: int | None,
    ) -> PairingOutcome:
        round_number = tournament.current_round + 1
        round_row = self._round_repo.add(
            Round(
                id=None,
                number=round_number,
                status=RoundStatus.ONGOING,
                generated_at=datetime.now(UTC),
            )
        )
        if round_row.id is None:
            raise ValueError("Не удалось создать тур.")

        persisted_games: list[Game] = []
        for game_data in pairing_data:
            table_number = int(game_data["table_number"])
            white_player_id = int(game_data["white_player_id"])
            black_player_id = int(game_data["black_player_id"])
            location = str(game_data.get("location", ""))
            persisted_games.append(
                self._game_repo.add(
                    Game(
                        id=None,
                        round_id=round_row.id,
                        board_number=table_number,
                        white_player_id=white_player_id,
                        black_player_id=black_player_id,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
            )
            self._update_player_board(
                white_player_id,
                board_number=table_number,
                location=location,
                color="White",
            )
            self._update_player_board(
                black_player_id,
                board_number=table_number,
                location=location,
                color="Black",
            )

        if bye_player_id is not None:
            bye_game = self._game_repo.add(
                Game(
                    id=None,
                    round_id=round_row.id,
                    board_number=len(persisted_games) + 1,
                    white_player_id=bye_player_id,
                    black_player_id=bye_player_id,
                    result=GameResult.BYE,
                    result_source="system",
                    is_bye=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            persisted_games.append(bye_game)
            bye_player = self._player_repo.get_by_id(bye_player_id)
            if bye_player is not None:
                bye_player.had_bye = True
                self._player_repo.update(bye_player)

        self._tournament_repo.update_status(
            tournament.status,
            prepared=tournament.prepared,
            number_of_rounds=tournament.number_of_rounds,
            current_round=round_number,
            rules_text=tournament.rules_text,
            pending_pairing_payload=None,
        )
        self._scoring_service.recalculate()
        return PairingOutcome(
            round_number=round_number,
            games=tuple(persisted_games),
            bye_player_id=bye_player_id,
            needs_confirmation=False,
            confirmation_reason=None,
        )

    def _update_player_board(self, player_id: int, *, board_number: int, location: str, color: str) -> None:
        player = self._player_repo.get_by_id(player_id)
        if player is None:
            return
        player.current_board = board_number
        player.seat_hint = f"Стол {board_number}, цвет: {color}, локация: {location}"
        self._player_repo.update(player)

