# Telegram Swiss Chess Bot

Telegram-бот для проведения одного шахматного турнира по швейцарской системе.

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
TOKEN=1234567890:AA...your_bot_token
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

## Команды по ролям
### PLAYER
- `/start`
- `/help`
- `/rules`
- `/register <username_or_user_id|me> <rating> <name>`
- `/get_game_id`
- `/my_next`
- `/schedule`
- `/my_score`
- `/standings [top_n]`
- `/report` (кнопки White/Black/Draw)
- `/create_ticket <arbitr|organizer> <описание>`
- `/close_ticket` (закрывает последний открытый тикет автора)

### ARBITRATOR
- Все player-команды, где допускает ACL
- `/approve_result <game_id> <result>`
- `/close_ticket <ticket_id>`

### ORGANIZER
- Все команды арбитра
- `/add_player <telegram_id|@username> <name>`
- `/disqualify <player_id>`
- `/tables`
- `/add_table <number> <location>`
- `/remove_table <number>`
- `/set_rules <text>`
- `/create_tournament <tables_count>`
- `/open_registration`
- `/set_round_number <n> [confirm]`
- `/prepare_turnament`
- `/start_tournament`
- `/tournament_statuc`
- `/end_round`
- `/next_round`
- `/confirm_next_round`
- `/round <n>`
- `/finish_tournament`
- `/undo_last_action`
- `/set_player_rating <player_id> <rating>`

## Логи
- Console: `DEBUG/INFO/WARNING/ERROR`
- Audit: файл `AUDIT_LOG_PATH` в JSON c полями:
  `timestamp, actor_id, roles, command, entity, before, after, result, reason`

## Минимальные сценарии
### 1. Подготовка и старт
1. Организатор: `/create_tournament 8`
2. Организатор: `/open_registration`
3. Игроки: `/register me 1500 Иван Иванов`
4. Организатор: `/set_round_number 5`
5. Организатор: `/prepare_turnament`
6. Организатор: `/start_tournament`

### 2. Проведение тура
1. Игрок: `/my_next`
2. Игрок: `/report` -> кнопка результата
3. При конфликте репортов: повтор `/report` или `/create_ticket arbitr ...`
4. Арбитр: `/approve_result <game_id> <result>` при споре
5. Организатор: `/end_round`, затем `/next_round`

### 3. Завершение
1. После последнего тура: `/end_round`
2. Организатор: `/finish_tournament`
3. Игроки: `/standings` и `/my_score`

## Тесты
```bash
python -m pytest
```

## Важные допущения
- В системе всегда один турнир (`id=1`).
- Рекомендация числа туров: `ceil(log2(N))`.
- Тай-брейки: `Buchholz > Median Buchholz > Sonneborn-Berger`.
- `forfeit` трактуется как победа белых (допущение фиксировано в коде).
- Подтверждение неустранимых повторов: `/next_round` -> `/confirm_next_round`.

