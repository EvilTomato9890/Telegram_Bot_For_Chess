"""Swiss pairing orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any, cast

from domain.dto import PairingOutcome
from domain.models import Game, GameResult, Player, PlayerStatus, Round, RoundStatus, Tournament, TournamentStatus
from repositories import GameRepository, PlayerRepository, RoundRepository, TableRepository, TournamentRepository

from .pairing_engine import InsufficientTablesError, PairingPlayer, TableSlot, generate_pairings
from .scoring_service import ScoringService


@dataclass(frozen=True, slots=True)
class _PendingPairing:
    """Normalized pending pairing payload stored in tournament row."""

    games: list[dict[str, Any]]
    bye_player_id: int | None
    needs_confirmation: bool
    confirmation_reason: str | None


class PairingService:
    """Generate rounds, persist pairings and build pre-start previews."""

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

    def prepare_next_round_preview(self, tournament_id: int, actor_id: int) -> PairingOutcome:
        """Build and persist preview pairings for prepared tournament before start."""

        del tournament_id, actor_id  # Single-tournament mode.
        tournament = self._require_prepared_registration_tournament()
        if tournament.current_round != 0:
            raise ValueError("Предпросмотр доступен только до старта первого тура.")

        pending = self._build_pending_from_engine()
        self._store_pending_payload(tournament, pending)
        self._apply_preview_to_players(pending.games, pending.bye_player_id)
        return PairingOutcome(
            round_number=1,
            games=tuple(self._preview_games_from_payload(pending.games)),
            bye_player_id=pending.bye_player_id,
            needs_confirmation=pending.needs_confirmation,
            confirmation_reason=pending.confirmation_reason,
        )

    def generate_next_round(self, tournament_id: int, actor_id: int, force: bool = False) -> PairingOutcome:
        """Generate next round pairings with optional forced repeats."""

        del tournament_id, actor_id  # Single-tournament mode.
        tournament = self._require_ongoing_tournament()
        self._validate_can_generate(tournament)

        pending = self._load_pending_payload(tournament)
        if pending is not None:
            if pending.needs_confirmation and not force:
                return PairingOutcome(
                    round_number=tournament.current_round + 1,
                    games=tuple(),
                    bye_player_id=pending.bye_player_id,
                    needs_confirmation=True,
                    confirmation_reason=pending.confirmation_reason,
                )
            return self._persist_generated_round(
                tournament=tournament,
                pairing_data=pending.games,
                bye_player_id=pending.bye_player_id,
            )

        built = self._build_pending_from_engine()
        if built.needs_confirmation and not force:
            self._store_pending_payload(tournament, built)
            return PairingOutcome(
                round_number=tournament.current_round + 1,
                games=tuple(),
                bye_player_id=built.bye_player_id,
                needs_confirmation=True,
                confirmation_reason=built.confirmation_reason,
            )

        return self._persist_generated_round(
            tournament=tournament,
            pairing_data=built.games,
            bye_player_id=built.bye_player_id,
        )

    def confirm_next_round(self, tournament_id: int, actor_id: int) -> PairingOutcome:
        """Force next round generation using the previously stored pending payload."""

        del tournament_id, actor_id
        tournament = self._require_ongoing_tournament()
        self._validate_can_generate(tournament)
        pending = self._load_pending_payload(tournament)
        if pending is None:
            raise ValueError("Нет ожидающего подтверждения генерации.")
        return self._persist_generated_round(
            tournament=tournament,
            pairing_data=pending.games,
            bye_player_id=pending.bye_player_id,
        )

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

    def _require_prepared_registration_tournament(self) -> Tournament:
        tournament = self._tournament_repo.get()
        if tournament is None:
            raise ValueError("Турнир не создан.")
        if tournament.status != TournamentStatus.REGISTRATION or not tournament.prepared:
            raise ValueError("Предпросмотр доступен только после /prepare_tournament и до /start_tournament.")
        return tournament

    def _build_pending_from_engine(self) -> _PendingPairing:
        active_players = [player for player in self._player_repo.list_all() if player.status == PlayerStatus.ACTIVE]
        if len(active_players) < 2:
            raise ValueError("Недостаточно активных игроков для генерации тура.")

        tables = self._table_repo.list_all()
        slots = [
            TableSlot(
                number=table.number,
                location=table.location,
                place=table.place_hint or "без уточнения",
            )
            for table in tables
        ]
        history = self._build_history(active_players)
        try:
            engine_result = generate_pairings(history, slots)
        except InsufficientTablesError as exc:
            required_tables = len(active_players) // 2
            raise ValueError(
                f"Недостаточно столов для генерации тура: нужно минимум {required_tables}, доступно {len(tables)}."
            ) from exc

        games = [
            {
                "table_number": game.table_number,
                "location": game.location,
                "white_player_id": game.white_player_id,
                "black_player_id": game.black_player_id,
            }
            for game in engine_result.games
        ]
        return _PendingPairing(
            games=games,
            bye_player_id=engine_result.bye.player_id if engine_result.bye is not None else None,
            needs_confirmation=engine_result.confirmation_request is not None,
            confirmation_reason=(
                engine_result.confirmation_request.reason
                if engine_result.confirmation_request is not None
                else None
            ),
        )

    def _build_history(self, active_players: list[Player]) -> list[PairingPlayer]:
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
                rating=player.rating,
                opponents=frozenset(opponents.get(player.id or 0, set())),
                color_history=tuple(colors.get(player.id or 0, [])),
                had_bye=had_bye.get(player.id or 0, False),
            )
            for player in active_players
        ]

    def _store_pending_payload(self, tournament: Tournament, pending: _PendingPairing) -> None:
        payload = {
            "games": pending.games,
            "bye_player_id": pending.bye_player_id,
            "needs_confirmation": pending.needs_confirmation,
            "reason": pending.confirmation_reason,
        }
        self._tournament_repo.update_status(
            tournament.status,
            prepared=tournament.prepared,
            number_of_rounds=tournament.number_of_rounds,
            current_round=tournament.current_round,
            rules_text=tournament.rules_text,
            pending_pairing_payload=json.dumps(payload, ensure_ascii=False),
        )

    def _load_pending_payload(self, tournament: Tournament) -> _PendingPairing | None:
        if not tournament.pending_pairing_payload:
            return None
        raw_payload = json.loads(tournament.pending_pairing_payload)
        if not isinstance(raw_payload, dict):
            raise ValueError("Некорректный pending payload для генерации тура.")
        raw_games = raw_payload.get("games", [])
        games: list[dict[str, Any]] = []
        if isinstance(raw_games, list):
            games = [cast(dict[str, Any], item) for item in raw_games if isinstance(item, dict)]

        raw_bye_player_id = raw_payload.get("bye_player_id")
        bye_player_id: int | None
        if isinstance(raw_bye_player_id, int):
            bye_player_id = raw_bye_player_id
        elif isinstance(raw_bye_player_id, str) and raw_bye_player_id.isdigit():
            bye_player_id = int(raw_bye_player_id)
        else:
            bye_player_id = None

        raw_confirm = raw_payload.get("needs_confirmation")
        needs_confirmation = bool(raw_confirm) if isinstance(raw_confirm, bool) else False
        raw_reason = raw_payload.get("reason")
        confirmation_reason = raw_reason if isinstance(raw_reason, str) and raw_reason.strip() else None
        return _PendingPairing(
            games=games,
            bye_player_id=bye_player_id,
            needs_confirmation=needs_confirmation,
            confirmation_reason=confirmation_reason,
        )

    def _preview_games_from_payload(self, pairing_data: list[dict[str, Any]]) -> list[Game]:
        now = datetime.now(UTC)
        preview_games: list[Game] = []
        for item in pairing_data:
            preview_games.append(
                Game(
                    id=None,
                    round_id=0,
                    board_number=int(item["table_number"]),
                    white_player_id=int(item["white_player_id"]),
                    black_player_id=int(item["black_player_id"]),
                    created_at=now,
                    updated_at=now,
                )
            )
        return preview_games

    def _apply_preview_to_players(self, pairing_data: list[dict[str, Any]], bye_player_id: int | None) -> None:
        # Clear outdated placements before writing preview.
        for player in self._player_repo.list_all():
            player.current_board = None
            player.seat_hint = None
            self._player_repo.update(player)

        for game_data in pairing_data:
            table_number = int(game_data["table_number"])
            location = str(game_data.get("location", ""))
            white_player_id = int(game_data["white_player_id"])
            black_player_id = int(game_data["black_player_id"])
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
            bye_player = self._player_repo.get_by_id(bye_player_id)
            if bye_player is not None:
                bye_player.current_board = None
                bye_player.seat_hint = "В следующем туре у вас bye (1 очко)."
                self._player_repo.update(bye_player)

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
            bye_board = max((int(item["table_number"]) for item in pairing_data), default=0) + 1
            bye_game = self._game_repo.add(
                Game(
                    id=None,
                    round_id=round_row.id,
                    board_number=bye_board,
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
                bye_player.current_board = None
                bye_player.seat_hint = "Технический bye (1 очко)."
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
