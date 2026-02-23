"""ACL service with command registry."""

from __future__ import annotations

from dataclasses import dataclass

from domain.dto import CommandSpec, HelpView
from domain.models import Role
from repositories import PlayerRepository, RoleGrantRepository


COMMAND_REGISTRY: tuple[CommandSpec, ...] = (
    CommandSpec("/help", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ORGANIZER}), "Список доступных команд"),
    CommandSpec("/start", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ORGANIZER}), "Стартовое меню"),
    CommandSpec("/rules", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ORGANIZER}), "Правила турнира"),
    CommandSpec("/get_game_id", frozenset({Role.PLAYER}), "ID своей последней/текущей партии"),
    CommandSpec("/my_next", frozenset({Role.PLAYER}), "Следующая партия"),
    CommandSpec("/schedule", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ORGANIZER}), "Расписание туров"),
    CommandSpec("/my_score", frozenset({Role.PLAYER}), "Мои очки и тай-брейки"),
    CommandSpec("/standings", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ORGANIZER}), "Таблица лидеров"),
    CommandSpec("/report", frozenset({Role.PLAYER}), "Сообщить результат своей партии"),
    CommandSpec("/register", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ORGANIZER}), "Регистрация участника"),
    CommandSpec("/create_ticket", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ORGANIZER}), "Создать тикет"),
    CommandSpec("/close_ticket", frozenset({Role.PLAYER, Role.ARBITRATOR, Role.ORGANIZER}), "Закрыть тикет"),
    CommandSpec("/approve_result", frozenset({Role.ARBITRATOR, Role.ORGANIZER}), "Подтвердить результат игры"),
    CommandSpec("/add_player", frozenset({Role.ORGANIZER}), "Добавить участника"),
    CommandSpec("/disqualify", frozenset({Role.ORGANIZER}), "Дисквалифицировать игрока"),
    CommandSpec("/tables", frozenset({Role.ORGANIZER}), "Список столов"),
    CommandSpec("/add_table", frozenset({Role.ORGANIZER}), "Добавить стол"),
    CommandSpec("/remove_table", frozenset({Role.ORGANIZER}), "Удалить стол"),
    CommandSpec("/set_rules", frozenset({Role.ORGANIZER}), "Задать регламент"),
    CommandSpec("/create_tournament", frozenset({Role.ORGANIZER}), "Создать черновик турнира"),
    CommandSpec("/open_registration", frozenset({Role.ORGANIZER}), "Открыть регистрацию"),
    CommandSpec("/set_round_number", frozenset({Role.ORGANIZER}), "Задать число туров"),
    CommandSpec("/prepare_turnament", frozenset({Role.ORGANIZER}), "Подготовить турнир"),
    CommandSpec("/start_tournament", frozenset({Role.ORGANIZER}), "Запустить турнир"),
    CommandSpec("/tournament_statuc", frozenset({Role.ORGANIZER}), "Состояние турнира"),
    CommandSpec("/end_round", frozenset({Role.ORGANIZER}), "Закрыть текущий тур"),
    CommandSpec("/next_round", frozenset({Role.ORGANIZER}), "Сгенерировать следующий тур"),
    CommandSpec("/confirm_next_round", frozenset({Role.ORGANIZER}), "Подтвердить генерацию с повторами"),
    CommandSpec("/round", frozenset({Role.ORGANIZER}), "Пары/результаты тура"),
    CommandSpec("/finish_tournament", frozenset({Role.ORGANIZER}), "Завершить турнир"),
    CommandSpec("/undo_last_action", frozenset({Role.ORGANIZER}), "Откат последнего действия организатора"),
    CommandSpec("/set_player_rating", frozenset({Role.ORGANIZER}), "Изменить рейтинг игрока"),
)


@dataclass(slots=True)
class AccessControlService:
    """Role resolution and ACL checks."""

    admin_ids: set[int]
    arbitrs_ids: set[int]
    role_grants_repo: RoleGrantRepository
    player_repo: PlayerRepository
    _PUBLIC_COMMANDS: frozenset[str] = frozenset({"/start", "/help", "/register"})

    def resolve_roles(self, telegram_id: int) -> set[Role]:
        """Resolve merged roles from config, runtime grants and player registrations."""

        roles: set[Role] = set()
        if telegram_id in self.admin_ids:
            roles.add(Role.ORGANIZER)
        if telegram_id in self.arbitrs_ids:
            roles.add(Role.ARBITRATOR)
        roles.update(self.role_grants_repo.resolve_roles(telegram_id))
        if self.player_repo.get_by_telegram_id(telegram_id) is not None:
            roles.add(Role.PLAYER)
        return roles

    def can_execute(self, telegram_id: int, command: str) -> bool:
        """Check if user can run command by OR-role policy."""

        if command in self._PUBLIC_COMMANDS:
            return True
        spec = self._find_spec(command)
        if spec is None:
            return False
        return bool(self.resolve_roles(telegram_id).intersection(spec.roles))

    def require(self, telegram_id: int, command: str) -> None:
        """Raise PermissionError when command is not allowed."""

        if not self.can_execute(telegram_id, command):
            raise PermissionError("Недостаточно прав для выполнения команды.")

    def help_for(self, telegram_id: int) -> HelpView:
        """Build help view of commands available for actor."""

        roles = self.resolve_roles(telegram_id)
        commands = tuple(
            spec
            for spec in COMMAND_REGISTRY
            if spec.name in self._PUBLIC_COMMANDS or spec.roles.intersection(roles)
        )
        return HelpView(actor_id=telegram_id, commands=commands)

    def user_ids_with_role(self, role: Role) -> list[int]:
        """Return known ids for organizer/arbitrator role queueing."""

        candidates: set[int] = set()
        if role == Role.ORGANIZER:
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

    @staticmethod
    def _find_spec(command: str) -> CommandSpec | None:
        for spec in COMMAND_REGISTRY:
            if spec.name == command:
                return spec
        return None
