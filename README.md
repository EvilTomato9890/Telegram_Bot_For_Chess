# Telegram Swiss Chess Bot

Telegram-бот для проведения шахматного турнира по швейцарской системе.

## Возможности
- Регистрация участников через `/start` (кнопка) и `/register`.
- Роли: игрок, арбитр, организатор (staff может быть одновременно игроком).
- Генерация пар по Swiss, учёт bye, пересчёт тай-брейков.
- Тикеты игрок -> арбитр/организатор с авто-назначением исполнителя.
- Поток туров `prepare -> next`:
  - `/prepare_round` подготавливает следующий тур и рассылает персональные места;
  - `/next_round` запускает только заранее подготовленный тур.
- Уведомление организаторов, когда все партии текущего тура завершены (тур закрывается только командой `/end_round`).

## Стек
- Python 3.11+
- aiogram 3.x
- SQLite
- `.env`-конфигурация

## Быстрый старт
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Инициализация БД:
```bash
python -m repositories.schema.init_db sqlite:///data/tournament.db
```

Запуск:
```bash
python main.py
```

## Конфигурация `.env`
Скопируйте `.env.example` в `.env` и заполните:

```env
TOKEN=1234567890:AA...real_bot_token
DB_URL=sqlite:///data/tournament.db
ADMIN_IDS=111111111
ARBITRS_IDS=222222222,333333333
TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
AUDIT_LOG_PATH=logs/audit.log
DEFAULT_RULES=Правила турнира...
STANDINGS_DEFAULT_TOP=10
```

## Роли
- `PLAYER`
- `ARBITRATOR`
- `ADMIN` (wire-value в БД: `organizer`)

ACL объединяет роли из:
- `ADMIN_IDS` / `ARBITRS_IDS` в `.env`;
- runtime role grants;
- факта регистрации пользователя в игроках.

Из-за этого staff-пользователь может иметь доступ и к player-командам, если он зарегистрирован как участник.

## Команды
`/help` показывает только доступные команды и группирует их по смыслу.

### Общие
- `/start`
- `/help`
- `/rules`
- `/schedule`
- `/standings [top_n]`

### Игрок
- `/register <rating> <имя и фамилия>`
- `/get_game_id`
- `/my_next`
- `/my_score`
- `/report`

### Тикеты
- `/create_ticket <arbitr|organizer> <описание>`
- `/close_ticket` — закрывает свой последний открытый тикет.
- `/close_ticket_by_id <ticket_id>` — закрытие по id (арбитр/организатор).
- `/ticket_queue`

Дополнительно по тикетам:
- В уведомлении арбитру указывается стол отправителя (если известен).
- В `/ticket_queue` для каждого тикета отображается стол автора.

### Арбитраж
- `/approve_result <game_id> <result> [confirm]`

### Участники (организатор)
- `/add_player <telegram_id|@username> <rating> <имя>`
- `/delete_player <player_id>`
- `/disqualify <player_id>`
- `/set_player_rating <player_id> <rating>`

### Столы (организатор)
- `/tables`
- `/add_table <номер> [локация]`
- `/remove_table <номер>`

Важно:
- Старый формат с `|` больше не поддерживается.
- Если локация не указана: `Локация не указана`.
- `place_hint` не используется в пользовательском UI (оставлен только для совместимости данных).

### Турнир (организатор)
- `/set_rules <текст>`
- `/announce <текст>`
- `/create_tournament`
- `/open_registration`
- `/set_round_number <n> [confirm]`
- `/prepare_tournament`
- `/start_tournament`
- `/prepare_round`
- `/next_round`
- `/confirm_next_round`
- `/end_round`
- `/round <n>`
- `/tournament_status`
- `/finish_tournament`
- `/force_finish_tournament` — принудительное завершение без обязательных проверок.

## Основной flow турнира
1. `/create_tournament`
2. `/add_table ...`
3. `/open_registration`
4. Регистрация игроков (`/start` или `/register`)
5. `/set_round_number <n>`
6. `/prepare_tournament`
7. `/start_tournament`

Дальше для каждого следующего тура:
1. Игроки/арбитры фиксируют результаты.
2. После завершения всех партий организаторы получают уведомление, что можно закрывать тур.
3. `/end_round`
4. `/prepare_round`
5. `/next_round` (или `/confirm_next_round`, если нужна генерация с повторами).

`/next_round` без `/prepare_round` запрещён.

## Ретро-изменение результата
`/approve_result` может требовать подтверждение организатора:
- если изменение затрагивает уже подготовленный, но ещё не начатый следующий тур;
- организатор подтверждает командой:
  `/approve_result <game_id> <result> confirm`.

После подтверждения происходит пересборка подготовленного тура и повторные уведомления участникам.

## Логи
- Обычные логи в консоль.
- Audit-log в JSON (`AUDIT_LOG_PATH`) с полями:
  `timestamp, actor_id, roles, command, entity, before, after, result, reason`.

## Проверка проекта
```bash
python -m pytest
python -m mypy --strict .
python -m compileall bot domain infra repositories services keyboards tests main.py
```

## Удалённое из runtime API
- Команда `/undo_last_action` удалена.
