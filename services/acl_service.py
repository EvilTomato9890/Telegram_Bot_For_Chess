"""ACL service with command registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain.dto import CommandSpec, HelpView
from domain.models import PlayerStatus, Role
from repositories import PlayerRepository, RoleGrantRepository


class PlayerAccessState(StrEnum):
    """Computed player access state used by ACL."""

    UNREGISTERED = "unregistered"
    PLAYER_ACTIVE = "player_active"
    PLAYER_DISQUALIFIED = "player_disqualified"


COMMAND_REGISTRY: tuple[CommandSpec, ...] = (
    CommandSpec("/help", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ADMIN}), "Список доступных команд", "Общие"),
    CommandSpec("/start", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ADMIN}), "Стартовое меню", "Общие"),
    CommandSpec("/rules", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ADMIN}), "Правила турнира", "Общие"),
    CommandSpec("/schedule", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ADMIN}), "Расписание туров", "Общие"),
    CommandSpec("/standings", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ADMIN}), "Таблица лидеров", "Общие"),
    CommandSpec("/register", frozenset({Role.PLAYER}), "Регистрация самого себя в турнире", "Игрок"),
    CommandSpec("/get_game_id", frozenset({Role.PLAYER}), "ID последней/текущей партии", "Игрок"),
    CommandSpec("/my_next", frozenset({Role.PLAYER}), "Следующая партия", "Игрок"),
    CommandSpec("/my_score", frozenset({Role.PLAYER}), "Мои очки и тай-брейки", "Игрок"),
    CommandSpec("/report", frozenset({Role.PLAYER}), "Сообщить результат своей партии", "Игрок"),
    CommandSpec("/create_ticket", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ADMIN}), "Создать тикет", "Тикеты"),
    CommandSpec(
        "/close_ticket",
        frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ADMIN}),
        "Закрыть тикет игрока-отправителя (свой последний открытый)",
        "Тикеты",
    ),
    CommandSpec(
        "/close_ticket_by_id",
        frozenset({Role.ARBITRATOR, Role.ADMIN}),
        "Закрыть тикет по ID (для арбитра/организатора)",
        "Тикеты",
    ),
    CommandSpec("/ticket_queue", frozenset({Role.ARBITRATOR, Role.ADMIN}), "Очередь активных тикетов арбитра", "Тикеты"),
    CommandSpec("/approve_result", frozenset({Role.ARBITRATOR, Role.ADMIN}), "Подтвердить результат игры", "Арбитраж"),
    CommandSpec("/add_player", frozenset({Role.ADMIN}), "Добавить участника", "Участники"),
    CommandSpec("/delete_player", frozenset({Role.ADMIN}), "Удалить участника из списка", "Участники"),
    CommandSpec("/disqualify", frozenset({Role.ADMIN}), "Дисквалифицировать игрока", "Участники"),
    CommandSpec("/set_player_rating", frozenset({Role.ADMIN}), "Изменить рейтинг игрока", "Участники"),
    CommandSpec("/tables", frozenset({Role.ADMIN}), "Список столов", "Столы"),
    CommandSpec("/add_table", frozenset({Role.ADMIN}), "Добавить стол", "Столы"),
    CommandSpec("/remove_table", frozenset({Role.ADMIN}), "Удалить стол", "Столы"),
    CommandSpec("/set_rules", frozenset({Role.ADMIN}), "Задать регламент", "Турнир"),
    CommandSpec("/announce", frozenset({Role.ADMIN}), "Объявление всем участникам", "Турнир"),
    CommandSpec("/create_tournament", frozenset({Role.ADMIN}), "Создать черновик турнира", "Турнир"),
    CommandSpec("/open_registration", frozenset({Role.ADMIN}), "Открыть регистрацию", "Турнир"),
    CommandSpec("/set_round_number", frozenset({Role.ADMIN}), "Задать число туров", "Турнир"),
    CommandSpec("/prepare_tournament", frozenset({Role.ADMIN}), "Подготовить турнир", "Турнир"),
    CommandSpec("/start_tournament", frozenset({Role.ADMIN}), "Запустить турнир", "Турнир"),
    CommandSpec("/prepare_round", frozenset({Role.ADMIN}), "Подготовить следующий тур", "Турнир"),
    CommandSpec("/tournament_status", frozenset({Role.ADMIN}), "Состояние турнира", "Турнир"),
    CommandSpec("/end_round", frozenset({Role.ADMIN}), "Закрыть текущий тур", "Турнир"),
    CommandSpec("/next_round", frozenset({Role.ADMIN}), "Запустить подготовленный тур", "Турнир"),
    CommandSpec("/confirm_next_round", frozenset({Role.ADMIN}), "Подтвердить генерацию с повторами", "Турнир"),
    CommandSpec("/round", frozenset({Role.ADMIN}), "Пары/результаты тура", "Турнир"),
    CommandSpec("/finish_tournament", frozenset({Role.ADMIN}), "Завершить турнир", "Турнир"),
)


@dataclass(slots=True)
class AccessControlService:
    """Role resolution and ACL checks."""

    admin_ids: set[int]
    arbitrs_ids: set[int]
    role_grants_repo: RoleGrantRepository
    player_repo: PlayerRepository
    _GUEST_ALLOWED: frozenset[str] = frozenset({"/start", "/help", "/register"})
    _DISQUALIFIED_ALLOWED: frozenset[str] = frozenset({"/help", "/rules", "/schedule", "/my_score", "/standings"})

    def resolve_roles(self, telegram_id: int) -> set[Role]:
        """Resolve merged roles from config, runtime grants and player registrations."""

        roles: set[Role] = set()
        if telegram_id in self.admin_ids:
            roles.add(Role.ADMIN)
        if telegram_id in self.arbitrs_ids:
            roles.add(Role.ARBITRATOR)
        roles.update(self.role_grants_repo.resolve_roles(telegram_id))
        if self.player_repo.get_by_telegram_id(telegram_id) is not None:
            roles.add(Role.PLAYER)
        return roles

    def resolve_player_access_state(self, telegram_id: int) -> PlayerAccessState:
        """Resolve computed access-state for player profile."""

        player = self.player_repo.get_by_telegram_id(telegram_id)
        if player is None:
            return PlayerAccessState.UNREGISTERED
        if player.status == PlayerStatus.DISQUALIFIED:
            return PlayerAccessState.PLAYER_DISQUALIFIED
        return PlayerAccessState.PLAYER_ACTIVE

    def can_execute(self, telegram_id: int, command: str) -> bool:
        """Check if user can run command by OR-role policy."""

        spec = self._find_spec(command)
        if spec is None:
            return False

        roles = self.resolve_roles(telegram_id)
        player_state = self.resolve_player_access_state(telegram_id)
        is_staff = Role.ADMIN in roles or Role.ARBITRATOR in roles

        if player_state == PlayerAccessState.UNREGISTERED and not is_staff:
            return command in self._GUEST_ALLOWED
        if player_state == PlayerAccessState.PLAYER_DISQUALIFIED and not is_staff:
            return command in self._DISQUALIFIED_ALLOWED

        if command in self._GUEST_ALLOWED:
            return True
        return bool(spec.roles.intersection(roles))

    def require(self, telegram_id: int, command: str) -> None:
        """Raise PermissionError when command is not allowed."""

        if self.can_execute(telegram_id, command):
            return
        raise PermissionError(self._permission_denied_message(telegram_id, command))

    def help_for(self, telegram_id: int) -> HelpView:
        """Build help view of commands available for actor."""

        commands = tuple(spec for spec in COMMAND_REGISTRY if self.can_execute(telegram_id, spec.name))
        return HelpView(actor_id=telegram_id, commands=commands)

    def user_ids_with_role(self, role: Role) -> list[int]:
        """Return known ids for admin/arbitrator role queueing."""

        candidates: set[int] = set()
        if role == Role.ADMIN:
            candidates.update(self.admin_ids)
        if role == Role.ARBITRATOR:
            candidates.update(self.arbitrs_ids)
        candidates.update(self.role_grants_repo.list_user_ids_with_role(role))
        return sorted(candidates)

    def grant_role(self, actor_id: int, target_id: int, role: Role) -> None:
        """Persist runtime grant. Caller must pass ACL checks."""

        self.require(actor_id, "/add_player")
        self.role_grants_repo.append(target_id, role, "grant")

    def revoke_role(self, actor_id: int, target_id: int, role: Role) -> None:
        """Persist runtime revoke. Caller must pass ACL checks."""

        self.require(actor_id, "/add_player")
        self.role_grants_repo.append(target_id, role, "revoke")

    def _permission_denied_message(self, telegram_id: int, command: str) -> str:
        player_state = self.resolve_player_access_state(telegram_id)
        roles = self.resolve_roles(telegram_id)
        is_staff = Role.ADMIN in roles or Role.ARBITRATOR in roles

        if command == "/register" and player_state != PlayerAccessState.UNREGISTERED:
            return "Вы уже зарегистрированы."
        if player_state == PlayerAccessState.UNREGISTERED and not is_staff:
            return "Команда недоступна до регистрации. Используйте /register."
        if player_state == PlayerAccessState.PLAYER_DISQUALIFIED and not is_staff:
            return "Команда недоступна для дисквалифицированного участника."
        return "Недостаточно прав для выполнения команды."

    @staticmethod
    def _find_spec(command: str) -> CommandSpec | None:
        for spec in COMMAND_REGISTRY:
            if spec.name == command:
                return spec
        return None
