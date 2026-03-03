# Telegram Swiss Chess Bot

Telegram-бот для проведения шахматного турнира по швейцарской системе.

## Технологии
- Python 3.11+
- aiogram v3
- SQLite (`sqlite3`)
- Конфигурация через `.env`
- Отдельный audit-log в JSON

## Структура проекта
```text
bot/
  app.py
  middleware/acl.py
  routers/common.py
  routers/player.py
  routers/arbitrator.py
  routers/organizer.py
  routers/fallback.py
domain/
  models/
  dto/
infra/
  config.py
  db.py
  logging.py
repositories/
  sqlite/
  migrations/
  schema/
services/
keyboards/
tests/
```

## Установка
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Конфиг `.env`
Скопируйте `.env.example` в `.env` и заполните значения:

```env
TOKEN=1234567890:AA...real_bot_token
DB_URL=sqlite:///data/tournament.db
ADMIN_IDS=111111111
ARBITRS_IDS=222222222,333333333
TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
AUDIT_LOG_PATH=logs/audit.log
DEFAULT_RULES=Правила турнира по швейцарской системе...
STANDINGS_DEFAULT_TOP=10
```

## Инициализация БД
```bash
python -m repositories.schema.init_db sqlite:///data/tournament.db
```

## Запуск
```bash
python main.py
```

## Роли
- `PLAYER`
- `ARBITRATOR`
- `ADMIN` (wire-value в БД: `organizer`)

## Команды по ролям

### PLAYER
- `/start`
- `/help`
- `/rules`
- `/register <rating> <name>`
- `/get_game_id`
- `/my_next`
- `/schedule`
- `/my_score`
- `/standings [top_n]` (доступно после старта турнира)
- `/report` (кнопки White/Black/Draw, только при активной партии)
- `/create_ticket <arbitr|organizer> <описание>`
- `/close_ticket` (закрывает последний открытый тикет автора)

### ARBITRATOR
- Все player-команды, где допускает ACL
- `/approve_result <game_id> <result>`
- `/ticket_queue`
- `/close_ticket <ticket_id>`

### ADMIN
- Все команды арбитра
- `/add_player <telegram_id|@username> <rating> <name>` (`@username` работает, если боту доступен `getChat` для пользователя)
- `/delete_player <player_id>`
- `/disqualify <player_id>`
- `/tables`
- `/add_table <number> <location> [| <place_hint>]`
- `/remove_table <number>`
- `/set_rules <text>`
- `/announce <text>`
- `/create_tournament`
- `/open_registration`
- `/set_round_number <n> [confirm]`
- `/prepare_tournament`
- `/start_tournament`
- `/tournament_status`
- `/end_round`
- `/next_round`
- `/confirm_next_round`
- `/round <n>`
- `/finish_tournament`
- `/undo_last_action`
- `/set_player_rating <player_id> <rating>`

## UX стартового экрана
- `/start` показывает 2 inline-кнопки:
  - `📝 Регистрация`
  - `🏆 Мой турнир`
- Кнопка `Регистрация` запускает пошаговый flow:
  - ввести рейтинг
  - ввести имя/фамилию
  - регистрация в турнир
- Кнопка `Мой турнир` открывает основное reply-меню игрока.

## Логи
- Console: `DEBUG/INFO/WARNING/ERROR`
- Audit: файл `AUDIT_LOG_PATH` в JSON с полями:
  `timestamp, actor_id, roles, command, entity, before, after, result, reason`

## Минимальные сценарии

### 1. Подготовка и старт
1. Админ: `/create_tournament`
2. Админ: `/add_table 1 Зал А`
3. Админ: `/add_table 2 Зал B`
4. Админ: `/open_registration`
5. Игроки: `/register 1500 Иван Иванов`
6. Админ: `/set_round_number 5`
7. Админ: `/prepare_tournament`
8. Админ: `/start_tournament`

### 2. Проведение тура
1. Игрок: `/my_next`
2. Игрок: `/report` -> кнопка результата
3. При конфликте отчетов: повтор `/report` или `/create_ticket arbitr ...`
4. Арбитр: `/ticket_queue`
5. Арбитр: `/approve_result <game_id> <result>` при споре
6. Админ: `/end_round`, затем `/next_round`

### 3. Завершение
1. После последнего тура: `/end_round`
2. Админ: `/finish_tournament`
3. Игроки: `/standings` и `/my_score`

## Тесты
```bash
python -m pytest
python -m mypy --strict .
python -m compileall bot domain infra repositories services keyboards tests main.py
```
