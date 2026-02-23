from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from handlers.common.response_formatter import ResponseFormatter


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
    registered_players: set[str] = field(default_factory=set)
    player_scores: dict[str, float] = field(default_factory=dict)
    reported_results: dict[str, str] = field(default_factory=dict)
    approved_results: set[str] = field(default_factory=set)
    open_tickets: dict[int, str] = field(default_factory=dict)
    next_ticket_id: int = 1


@dataclass(slots=True)
class CommandRecord:
    command: str
    snapshot: TournamentState


@dataclass(frozen=True, slots=True)
class AuditRecord:
    actor: str
    command: str
    timestamp: str
    outcome: str


class NotificationService:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def _push(self, message: str) -> str:
        self.messages.append(message)
        return message

    def round_started(self, round_number: int) -> str:
        return self._push(f"Notification: round {round_number} started")

    def round_ended(self, round_number: int) -> str:
        return self._push(f"Notification: round {round_number} ended")

    def pairs_published(self, round_number: int) -> str:
        return self._push(f"Notification: pairings for round {round_number} published")

    def rules_updated(self) -> str:
        return self._push("Notification: tournament rules updated")

    def tournament_finished(self, player: str, position: int) -> str:
        return self._push(f"Notification: tournament finished, {player} position #{position}")


class ScheduleService:
    def round_windows(self, total_rounds: int) -> tuple[str, ...]:
        if total_rounds < 1:
            return ()
        return tuple(
            f"Round {round_number}: day {2 * round_number - 1} 10:00-22:00"
            for round_number in range(1, total_rounds + 1)
        )


class TournamentService:
    CRITICAL_COMMANDS = {
        "/create_tournament",
        "/open_registration",
        "/set_round_number",
        "/set_player_rating",
        "/prepare_turnament",
        "/start_tournament",
        "/end_round",
        "/next_round",
        "/finish_tournament",
        "/update_rules",
        "/approve_result",
        "/close_ticket",
    }

    def __init__(
        self,
        notification_service: NotificationService | None = None,
        schedule_service: ScheduleService | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.state = TournamentState()
        self.command_log: list[CommandRecord] = []
        self.audit_log: list[AuditRecord] = []
        self.notification_service = notification_service or NotificationService()
        self.schedule_service = schedule_service or ScheduleService()
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def _log_critical(self, command: str, outcome: str, actor: str = "system") -> None:
        if command not in self.CRITICAL_COMMANDS:
            return
        timestamp = self._now_provider().isoformat()
        print(f"[critical] actor={actor} command={command} timestamp={timestamp} outcome={outcome}")
        self.audit_log.append(
            AuditRecord(actor=actor, command=command, timestamp=timestamp, outcome=outcome)
        )

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
        message = "Tournament created"
        self._log_critical("/create_tournament", message)
        return message

    def open_registration(self) -> str:
        self._ensure_status(
            (TournamentStatus.CREATED,),
            reason="Registration can only be opened after tournament creation",
        )
        return self._record("/open_registration", self._open_registration_impl)

    def _open_registration_impl(self) -> str:
        self.state.status = TournamentStatus.REGISTRATION_OPEN
        message = "Registration opened"
        self._log_critical("/open_registration", message)
        return message

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
        message = f"Round number set to {rounds}"
        self._log_critical("/set_round_number", message)
        return message

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
        message = f"Rating for {player} set to {rating}"
        self._log_critical("/set_player_rating", message, actor=player)
        return message

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
        message = "Tournament prepared"
        self._log_critical("/prepare_turnament", message)
        return message

    def start_tournament(self) -> str:
        self._ensure_status(
            (TournamentStatus.PREPARED,),
            reason="Tournament can only be started after preparation",
        )
        return self._record("/start_tournament", self._start_tournament_impl)

    def _start_tournament_impl(self) -> str:
        self.state.current_round = 1
        self.state.status = TournamentStatus.ROUND_OPEN
        self.notification_service.round_started(1)
        self.notification_service.pairs_published(1)
        message = "Tournament started, round 1 opened"
        self._log_critical("/start_tournament", message)
        return message

    def end_round(self) -> str:
        self._ensure_status((TournamentStatus.ROUND_OPEN,), reason="Can only end an opened round")
        return self._record("/end_round", self._end_round_impl)

    def _end_round_impl(self) -> str:
        self.state.rounds_closed.add(self.state.current_round)
        self.state.status = TournamentStatus.ROUND_CLOSED
        self.notification_service.round_ended(self.state.current_round)
        message = f"Round {self.state.current_round} ended"
        self._log_critical("/end_round", message)
        return message

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
        self.notification_service.round_started(self.state.current_round)
        self.notification_service.pairs_published(self.state.current_round)
        message = f"Round {self.state.current_round} opened"
        self._log_critical("/next_round", message)
        return message

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
        position = self._player_position("me")
        self.notification_service.tournament_finished("me", position)
        message = "Tournament finished"
        self._log_critical("/finish_tournament", message)
        return message

    def _player_position(self, player: str) -> int:
        sorted_players = sorted(
            self.state.player_scores.items(), key=lambda item: (-item[1], item[0])
        )
        for idx, (name, _) in enumerate(sorted_players, start=1):
            if name == player:
                return idx
        return len(sorted_players) + 1

    def tournament_status(self) -> str:
        status = self.state.status.value
        if self.state.current_round:
            return f"status={status}, round={self.state.current_round}/{self.state.total_rounds}"
        return f"status={status}, rounds={self.state.total_rounds}"

    def tournament_statuc(self) -> str:
        """Backward-compatible typo alias."""
        return self.tournament_status()

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

    def rules(self) -> str:
        return ResponseFormatter.rules()

    def get_game_id(self) -> str:
        game_id = f"R{max(1, self.state.current_round)}-B1"
        return ResponseFormatter.get_game_id(game_id)

    def my_next(self) -> str:
        return ResponseFormatter.my_next("board 1, white vs black")

    def schedule(self) -> str:
        windows = self.schedule_service.round_windows(self.state.total_rounds)
        if not windows:
            current_round = max(1, self.state.current_round)
            return ResponseFormatter.schedule(self.state.total_rounds, current_round)
        return ResponseFormatter.schedule_windows(windows)

    def update_rules(self) -> str:
        self.notification_service.rules_updated()
        message = "Rules updated"
        self._log_critical("/update_rules", message)
        return message

    def my_score(self) -> str:
        score = self.state.player_scores.get("me", 0.0)
        return ResponseFormatter.my_score(score)

    def standings(self) -> str:
        total_players = len(self.state.registered_players)
        return ResponseFormatter.standings(total_players)

    def report(self, game_id: str, result: str) -> str:
        return self._record("/report", lambda: self._report_impl(game_id, result))

    def _report_impl(self, game_id: str, result: str) -> str:
        self.state.reported_results[game_id] = result
        return ResponseFormatter.report_received(game_id, result)

    def register(self) -> str:
        return self._record("/register", self._register_impl)

    def _register_impl(self) -> str:
        self.state.registered_players.add("me")
        return ResponseFormatter.player_registered()

    def create_ticket(self, topic: str) -> str:
        return self._record("/create_ticket", lambda: self._create_ticket_impl(topic))

    def _create_ticket_impl(self, topic: str) -> str:
        ticket_id = self.state.next_ticket_id
        self.state.next_ticket_id += 1
        self.state.open_tickets[ticket_id] = topic
        return ResponseFormatter.ticket_created(ticket_id, topic)

    def close_ticket(self, ticket_id: int) -> str:
        if ticket_id not in self.state.open_tickets:
            raise CommandError(ResponseFormatter.ticket_not_found(ticket_id))
        return self._record("/close_ticket", lambda: self._close_ticket_impl(ticket_id))

    def _close_ticket_impl(self, ticket_id: int) -> str:
        del self.state.open_tickets[ticket_id]
        message = ResponseFormatter.ticket_closed(ticket_id)
        self._log_critical("/close_ticket", message)
        return message

    def approve_result(self, game_id: str) -> str:
        if game_id not in self.state.reported_results:
            raise CommandError(ResponseFormatter.no_reported_result(game_id))
        return self._record("/approve_result", lambda: self._approve_result_impl(game_id))

    def _approve_result_impl(self, game_id: str) -> str:
        self.state.approved_results.add(game_id)
        message = ResponseFormatter.result_approved(game_id)
        self._log_critical("/approve_result", message)
        return message


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
            raise CommandError(ResponseFormatter.EMPTY_COMMAND_ERROR)

        command = tokens[0]
        if command == "/create_tournament":
            return self.service.create_tournament()
        if command == "/open_registration":
            return self.service.open_registration()
        if command == "/set_round_number":
            if len(tokens) != 2:
                raise CommandError(ResponseFormatter.USAGE_SET_ROUND)
            rounds = self._parse_int(tokens[1], usage=ResponseFormatter.USAGE_SET_ROUND)
            return self.service.set_round_number(rounds)
        if command == "/set_player_rating":
            if len(tokens) != 3:
                raise CommandError(ResponseFormatter.USAGE_SET_PLAYER_RATING)
            rating = self._parse_int(tokens[2], usage=ResponseFormatter.USAGE_SET_PLAYER_RATING)
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
            return self.service.tournament_status()
        if command == "/round":
            if len(tokens) != 2:
                raise CommandError(ResponseFormatter.USAGE_ROUND)
            round_number = self._parse_int(tokens[1], usage=ResponseFormatter.USAGE_ROUND)
            return self.service.round_info(round_number)
        if command == "/undo_last_action":
            return self.service.undo_last_action()

        if command == "/rules":
            return self.service.rules()
        if command == "/get_game_id":
            return self.service.get_game_id()
        if command == "/my_next":
            return self.service.my_next()
        if command == "/schedule":
            return self.service.schedule()
        if command == "/update_rules":
            return self.service.update_rules()
        if command == "/my_score":
            return self.service.my_score()
        if command == "/standings":
            return self.service.standings()
        if command == "/report":
            if len(tokens) != 3:
                raise CommandError(ResponseFormatter.USAGE_REPORT)
            return self.service.report(tokens[1], tokens[2])
        if command == "/register":
            return self.service.register()
        if command == "/create_ticket":
            if len(tokens) < 2:
                raise CommandError(ResponseFormatter.USAGE_CREATE_TICKET)
            return self.service.create_ticket(" ".join(tokens[1:]))
        if command == "/close_ticket":
            if len(tokens) != 2:
                raise CommandError(ResponseFormatter.USAGE_CLOSE_TICKET)
            ticket_id = self._parse_int(tokens[1], usage=ResponseFormatter.USAGE_CLOSE_TICKET)
            return self.service.close_ticket(ticket_id)
        if command == "/approve_result":
            if len(tokens) != 2:
                raise CommandError(ResponseFormatter.USAGE_APPROVE_RESULT)
            return self.service.approve_result(tokens[1])
        if command == "/help":
            if len(tokens) > 1 and tokens[1].lower() == "arbitrator":
                return ResponseFormatter.HELP_ARBITRATOR
            return ResponseFormatter.HELP_PLAYER

        raise CommandError(ResponseFormatter.unknown_command(command))
