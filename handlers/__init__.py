from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class CommandError(ValueError):
    """Raised when command cannot be executed in current tournament status."""


class TournamentStatus(str, Enum):
    NOT_CREATED = "not_created"
    CREATED = "created"
    REGISTRATION_OPEN = "registration_open"
    PREPARED = "prepared"
    ROUND_OPEN = "round_open"
    ROUND_CLOSED = "round_closed"
    FINISHED = "finished"


@dataclass(slots=True)
class TournamentState:
    status: TournamentStatus = TournamentStatus.NOT_CREATED
    total_rounds: int = 0
    current_round: int = 0
    players_ratings_locked: bool = False
    rounds_closed: set[int] = field(default_factory=set)
    players_ratings: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class CommandRecord:
    command: str
    snapshot: TournamentState


class TournamentService:
    def __init__(self) -> None:
        self.state = TournamentState()
        self.command_log: list[CommandRecord] = []

    def _record(self, command: str, action: Callable[[], str]) -> str:
        snapshot = copy.deepcopy(self.state)
        message = action()
        self.command_log.append(CommandRecord(command=command, snapshot=snapshot))
        return message

    def _ensure_status(
        self,
        allowed: tuple[TournamentStatus, ...],
        *,
        reason: str,
    ) -> None:
        if self.state.status not in allowed:
            raise CommandError(reason)

    def create_tournament(self) -> str:
        self._ensure_status(
            (TournamentStatus.NOT_CREATED, TournamentStatus.FINISHED),
            reason="Cannot create a new tournament until current one is finished",
        )
        return self._record("/create_tournament", self._create_tournament_impl)

    def _create_tournament_impl(self) -> str:
        self.state = TournamentState(status=TournamentStatus.CREATED)
        return "Tournament created"

    def open_registration(self) -> str:
        self._ensure_status(
            (TournamentStatus.CREATED,),
            reason="Registration can only be opened after tournament creation",
        )
        return self._record("/open_registration", self._open_registration_impl)

    def _open_registration_impl(self) -> str:
        self.state.status = TournamentStatus.REGISTRATION_OPEN
        return "Registration opened"

    def set_round_number(self, rounds: int) -> str:
        self._ensure_status(
            (TournamentStatus.CREATED, TournamentStatus.REGISTRATION_OPEN),
            reason="Round number can only be set before preparation",
        )
        if rounds < 1:
            raise CommandError("Round number must be positive")
        return self._record("/set_round_number", lambda: self._set_round_number_impl(rounds))

    def _set_round_number_impl(self, rounds: int) -> str:
        self.state.total_rounds = rounds
        return f"Round number set to {rounds}"

    def set_player_rating(self, player: str, rating: int) -> str:
        if self.state.players_ratings_locked:
            raise CommandError("Cannot change player ratings after /prepare_turnament")
        self._ensure_status(
            (TournamentStatus.CREATED, TournamentStatus.REGISTRATION_OPEN),
            reason="Player ratings can only be set before preparation",
        )
        if rating <= 0:
            raise CommandError("Player rating must be positive")
        return self._record(
            "/set_player_rating",
            lambda: self._set_player_rating_impl(player, rating),
        )

    def _set_player_rating_impl(self, player: str, rating: int) -> str:
        self.state.players_ratings[player] = rating
        return f"Rating for {player} set to {rating}"

    def prepare_turnament(self) -> str:
        self._ensure_status(
            (TournamentStatus.REGISTRATION_OPEN,),
            reason="Tournament can only be prepared after registration is opened",
        )
        if self.state.total_rounds < 1:
            raise CommandError("Set total rounds before preparation")
        return self._record("/prepare_turnament", self._prepare_turnament_impl)

    def _prepare_turnament_impl(self) -> str:
        self.state.status = TournamentStatus.PREPARED
        self.state.players_ratings_locked = True
        return "Tournament prepared"

    def start_tournament(self) -> str:
        self._ensure_status(
            (TournamentStatus.PREPARED,),
            reason="Tournament can only be started after preparation",
        )
        return self._record("/start_tournament", self._start_tournament_impl)

    def _start_tournament_impl(self) -> str:
        self.state.current_round = 1
        self.state.status = TournamentStatus.ROUND_OPEN
        return "Tournament started, round 1 opened"

    def end_round(self) -> str:
        self._ensure_status((TournamentStatus.ROUND_OPEN,), reason="Can only end an opened round")
        return self._record("/end_round", self._end_round_impl)

    def _end_round_impl(self) -> str:
        self.state.rounds_closed.add(self.state.current_round)
        self.state.status = TournamentStatus.ROUND_CLOSED
        return f"Round {self.state.current_round} ended"

    def next_round(self) -> str:
        self._ensure_status(
            (TournamentStatus.ROUND_CLOSED,),
            reason="Cannot generate/start next round while current round is not closed",
        )
        if self.state.current_round >= self.state.total_rounds:
            raise CommandError("No more rounds left")
        return self._record("/next_round", self._next_round_impl)

    def _next_round_impl(self) -> str:
        self.state.current_round += 1
        self.state.status = TournamentStatus.ROUND_OPEN
        return f"Round {self.state.current_round} opened"

    def finish_tournament(self) -> str:
        self._ensure_status(
            (TournamentStatus.ROUND_CLOSED,),
            reason="Tournament can be finished only when a round is closed",
        )
        if self.state.current_round != self.state.total_rounds:
            raise CommandError("Cannot finish tournament before the last round")
        return self._record("/finish_tournament", self._finish_tournament_impl)

    def _finish_tournament_impl(self) -> str:
        self.state.status = TournamentStatus.FINISHED
        return "Tournament finished"

    def tournament_statuc(self) -> str:
        status = self.state.status.value
        if self.state.current_round:
            return f"status={status}, round={self.state.current_round}/{self.state.total_rounds}"
        return f"status={status}, rounds={self.state.total_rounds}"

    def round_info(self, round_number: int) -> str:
        if self.state.total_rounds < 1:
            raise CommandError("Rounds are not configured")
        if round_number < 1 or round_number > self.state.total_rounds:
            raise CommandError("Round number is out of range")
        is_closed = round_number in self.state.rounds_closed
        marker = "closed" if is_closed else "open_or_future"
        return f"round={round_number}, status={marker}"

    def undo_last_action(self) -> str:
        if not self.command_log:
            raise CommandError("No actions to undo")
        last = self.command_log.pop()
        self.state = last.snapshot
        return f"Undone: {last.command}"


class CommandDispatcher:
    def __init__(self, service: TournamentService | None = None) -> None:
        self.service = service or TournamentService()

    @staticmethod
    def _parse_int(value: str, *, usage: str) -> int:
        try:
            return int(value)
        except ValueError as error:
            raise CommandError(usage) from error

    def execute(self, command_text: str) -> str:
        tokens = command_text.strip().split()
        if not tokens:
            raise CommandError("Empty command")

        command = tokens[0]
        if command == "/create_tournament":
            return self.service.create_tournament()
        if command == "/open_registration":
            return self.service.open_registration()
        if command == "/set_round_number":
            if len(tokens) != 2:
                raise CommandError("Usage: /set_round_number <n>")
            rounds = self._parse_int(tokens[1], usage="Usage: /set_round_number <n>")
            return self.service.set_round_number(rounds)
        if command == "/set_player_rating":
            if len(tokens) != 3:
                raise CommandError("Usage: /set_player_rating <player> <rating>")
            rating = self._parse_int(
                tokens[2],
                usage="Usage: /set_player_rating <player> <rating>",
            )
            return self.service.set_player_rating(tokens[1], rating)
        if command in {"/prepare_turnament", "/prepare_tournament"}:
            return self.service.prepare_turnament()
        if command == "/start_tournament":
            return self.service.start_tournament()
        if command == "/end_round":
            return self.service.end_round()
        if command == "/next_round":
            return self.service.next_round()
        if command == "/finish_tournament":
            return self.service.finish_tournament()
        if command in {"/tournament_statuc", "/tournament_status"}:
            return self.service.tournament_statuc()
        if command == "/round":
            if len(tokens) != 2:
                raise CommandError("Usage: /round <n>")
            round_number = self._parse_int(tokens[1], usage="Usage: /round <n>")
            return self.service.round_info(round_number)
        if command == "/undo_last_action":
            return self.service.undo_last_action()

        raise CommandError(f"Unknown command: {command}")
