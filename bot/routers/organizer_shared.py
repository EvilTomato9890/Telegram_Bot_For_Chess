"""Shared helpers for admin (organizer) command routers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from aiogram.types import Message

from domain.exceptions import DomainError
from domain.models import Game, Player, PlayerStatus, Role, RoundStatus
from infra.logging import AuditLogger
from repositories import GameRepository, PlayerRepository, RoundRepository, TableRepository
from services import (
    AccessControlService,
    NotificationGateway,
    NotificationService,
    PairingService,
    RegistrationService,
    ScoringService,
    TournamentService,
    UndoService,
)

_T = TypeVar("_T")


@dataclass(slots=True, frozen=True)
class OrganizerShared:
    """Helper facade reused by split admin router modules."""

    acl: AccessControlService
    registration_service: RegistrationService
    tournament_service: TournamentService
    pairing_service: PairingService
    scoring_service: ScoringService
    undo_service: UndoService
    player_repo: PlayerRepository
    round_repo: RoundRepository
    game_repo: GameRepository
    table_repo: TableRepository
    audit_logger: AuditLogger
    notification_service: NotificationService
    notification_gateway: NotificationGateway | None = None

    def admin_check(self, message: Message, command: str) -> int:
        """Validate command ACL and return actor telegram id."""

        if message.from_user is None:
            raise DomainError("Не удалось определить пользователя.")
        self.acl.require(message.from_user.id, command)
        return message.from_user.id

    def log_ok(
        self,
        actor: int,
        command: str,
        entity: str,
        after: dict[str, object],
        before: dict[str, object] | None = None,
    ) -> None:
        """Write one successful audit event."""

        self.audit_logger.log_event(
            actor_id=actor,
            roles=[role.value for role in self.acl.resolve_roles(actor)],
            command=command,
            entity=entity,
            before=before,
            after=after,
            result="ok",
            reason=None,
        )

    @staticmethod
    def parse_int(raw: str, *, field: str) -> int:
        """Parse integer command argument with domain-friendly error."""

        try:
            return int(raw)
        except ValueError as exc:
            raise DomainError(f"{field} должен быть числом.") from exc

    def _take_snapshot(self, actor: int, command: str) -> int:
        snapshot = self.undo_service.snapshot(actor, command)
        if snapshot.id is None:
            raise DomainError("Не удалось сохранить undo-снапшот.")
        return snapshot.id

    def run_with_snapshot(self, actor: int, command: str, mutate: Callable[[], _T]) -> _T:
        """Execute mutation under snapshot protection."""

        self._take_snapshot(actor, command)
        return mutate()

    async def notify_players(
        self,
        message: Message,
        text_builder: Callable[[Player], str],
        *,
        include_disqualified: bool = True,
    ) -> None:
        """Notify all registered players; delivery failures are tolerated."""

        bot = message.bot
        for player in self.player_repo.list_all():
            if not include_disqualified and player.status == PlayerStatus.DISQUALIFIED:
                continue
            text = text_builder(player)
            if self.notification_gateway is not None:
                await self.notification_gateway.send_to_user(bot, player.telegram_id, text)
                continue
            self.notification_service.notify(f"[TO:{player.telegram_id}] {text}")
            if bot is None:
                continue
            try:
                await bot.send_message(player.telegram_id, text)
            except Exception:  # noqa: BLE001
                continue

    async def notify_admins(self, message: Message, text: str) -> None:
        """Notify all admins."""

        bot = message.bot
        admin_ids = self.acl.user_ids_with_role(Role.ADMIN)
        for admin_id in admin_ids:
            if self.notification_gateway is not None:
                await self.notification_gateway.send_to_user(bot, admin_id, text)
                continue
            self.notification_service.notify(f"[ADMIN:{admin_id}] {text}")
            if bot is None:
                continue
            try:
                await bot.send_message(admin_id, text)
            except Exception:  # noqa: BLE001
                continue

    @staticmethod
    async def send_long_message(message: Message, text: str) -> None:
        """Send long text by chunks accepted by Telegram."""

        chunk_size = 3500
        if len(text) <= chunk_size:
            await message.answer(text)
            return
        start = 0
        while start < len(text):
            await message.answer(text[start : start + chunk_size])
            start += chunk_size

    def render_round_games(self, round_number: int, games: tuple[Game, ...]) -> list[str]:
        """Render compact round game lines."""

        lines: list[str] = []
        for game in games:
            white = self.player_repo.get_by_id(game.white_player_id)
            black = self.player_repo.get_by_id(game.black_player_id)
            white_name = white.full_name if white is not None else str(game.white_player_id)
            black_name = black.full_name if black is not None else str(game.black_player_id)
            if game.is_bye:
                lines.append(f"Тур {round_number}: {white_name} получает bye (1 очко)")
            else:
                lines.append(f"Тур {round_number}: стол {game.board_number} - {white_name} vs {black_name}")
        return lines

    def preview_messages_by_player(
        self,
        preview_games: tuple[Game, ...],
        bye_player_id: int | None,
    ) -> dict[int, str]:
        """Build per-player preview messages for prepared tournament."""

        messages: dict[int, str] = {}
        for game in preview_games:
            table = self.table_repo.get_by_number(game.board_number)
            location = table.location if table is not None else "неизвестно"
            white = self.player_repo.get_by_id(game.white_player_id)
            black = self.player_repo.get_by_id(game.black_player_id)
            white_name = white.full_name if white is not None else f"id={game.white_player_id}"
            black_name = black.full_name if black is not None else f"id={game.black_player_id}"
            messages[game.white_player_id] = (
                f"Предварительная информация: стол {game.board_number}, цвет White, "
                f"соперник {black_name}, локация: {location}"
            )
            messages[game.black_player_id] = (
                f"Предварительная информация: стол {game.board_number}, цвет Black, "
                f"соперник {white_name}, локация: {location}"
            )
        if bye_player_id is not None:
            messages[bye_player_id] = "Предварительная информация: в первом туре у вас bye (1 очко)."
        return messages

    def validate_end_round_precheck(self) -> bool:
        """Validate /end_round before snapshot; return False when round is already closed."""

        current = self.round_repo.get_current()
        if current is None:
            tournament = self.tournament_service.ensure_tournament()
            if tournament.current_round <= 0:
                raise DomainError("Нет активного тура.")
            last_round = self.round_repo.get_by_number(tournament.current_round)
            if last_round is None:
                raise DomainError("Нет активного тура.")
            if last_round.status == RoundStatus.CLOSED:
                return False
            current = last_round

        if current.status == RoundStatus.CLOSED:
            return False
        if current.id is None:
            raise DomainError("Не удалось определить идентификатор текущего тура.")

        games = self.game_repo.list_by_round(current.id)
        if not games or any(game.result is None for game in games):
            raise DomainError("Нельзя закрыть тур: не все результаты зафиксированы.")
        return True

