from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KeyboardMessage:
    text: str
    buttons: tuple[str, ...]


class ResponseFormatter:
    """Centralized success/error message templates to avoid text duplication."""

    EMPTY_COMMAND_ERROR = "Empty command"
    UNKNOWN_COMMAND_ERROR = "Unknown command: {command}"
    USAGE_SET_ROUND = "Usage: /set_round_number <n>"
    USAGE_SET_PLAYER_RATING = "Usage: /set_player_rating <player> <rating>"
    USAGE_ROUND = "Usage: /round <n>"
    USAGE_REPORT = "Usage: /report <game_id> <result>"
    USAGE_APPROVE_RESULT = "Usage: /approve_result <game_id>"
    USAGE_CLOSE_TICKET = "Usage: /close_ticket <ticket_id>"
    USAGE_CREATE_TICKET = "Usage: /create_ticket <topic>"

    HELP_PLAYER = (
        "Player commands:\n"
        "/rules, /get_game_id, /my_next, /schedule, /my_score, /standings, /report, "
        "/register, /create_ticket, /close_ticket, /help"
    )
    HELP_ARBITRATOR = "Arbitrator commands:\n/approve_result, /close_ticket, /help"

    START_KEYBOARD_TEXT = "Добро пожаловать в турнирного бота!"

    @staticmethod
    def unknown_command(command: str) -> str:
        return ResponseFormatter.UNKNOWN_COMMAND_ERROR.format(command=command)

    @staticmethod
    def rules() -> str:
        return (
            "Правила: играйте по расписанию, сообщайте результат через /report, "
            "при споре создавайте тикет через /create_ticket."
        )

    @staticmethod
    def get_game_id(game_id: str) -> str:
        return f"Your current game id: {game_id}"

    @staticmethod
    def my_next(next_pairing: str) -> str:
        return f"Your next game: {next_pairing}"

    @staticmethod
    def schedule(total_rounds: int, current_round: int) -> str:
        if total_rounds < 1:
            return "Schedule is not published yet"
        return f"Schedule: round {current_round}/{total_rounds} is active"

    @staticmethod
    def schedule_windows(windows: tuple[str, ...]) -> str:
        if not windows:
            return "Schedule is not published yet"
        return "Schedule windows:\n" + "\n".join(windows)

    @staticmethod
    def my_score(score: float) -> str:
        return f"Your score: {score:.1f}"

    @staticmethod
    def standings(total_players: int) -> str:
        return f"Standings are available: {total_players} players"

    @staticmethod
    def report_received(game_id: str, result: str) -> str:
        return f"Result for {game_id} reported as {result} and awaits arbitrator approval"

    @staticmethod
    def player_registered() -> str:
        return "You are registered for the tournament"

    @staticmethod
    def ticket_created(ticket_id: int, topic: str) -> str:
        return f"Ticket #{ticket_id} created: {topic}"

    @staticmethod
    def ticket_closed(ticket_id: int) -> str:
        return f"Ticket #{ticket_id} closed"

    @staticmethod
    def result_approved(game_id: str) -> str:
        return f"Result for {game_id} approved"

    @staticmethod
    def no_reported_result(game_id: str) -> str:
        return f"No reported result for {game_id}"

    @staticmethod
    def ticket_not_found(ticket_id: int) -> str:
        return f"Ticket #{ticket_id} not found or already closed"
