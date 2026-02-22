# Telegram Bot for Chess

Telegram-бот для проведения шахматных турниров по швейцарской системе.

## 1. Требования

- **Python**: `3.11+`.
- **База данных**:
  - по умолчанию используется `SQLite` через `aiosqlite`;
  - можно использовать любую БД с async-драйвером SQLAlchemy (PostgreSQL/MySQL и т.д.) при корректном `DATABASE_URL`.
- **Пакетный менеджер**: `pip`.

## 2. Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .[dev]
cp .env.example .env
```

Далее заполните `.env` и выполните:

```bash
alembic upgrade head
python -m bot.main
```

## 3. Конфигурация (.env)

Проект читает настройки из `.env` (см. пример в `.env.example`).

```env
TOKEN=123456:telegram-token
ADMIN_IDS=123456789,987654321
TIMEZONE=UTC
DATABASE_URL=sqlite+aiosqlite:///./tournaments.db
AUTO_ADVANCE_TO_NEXT_ROUND=false
MODERATE_RESULTS=true
LOG_LEVEL=INFO
```

### Обязательные переменные

- `TOKEN` — токен Telegram-бота (получается у BotFather).

### Основные переменные

- `ADMIN_IDS` — CSV-список Telegram user id организаторов.
  - Пример: `123456789,987654321`
- `TIMEZONE` — IANA timezone.
  - Примеры: `UTC`, `Europe/Moscow`, `Asia/Almaty`
- `DATABASE_URL` — строка подключения SQLAlchemy.
  - SQLite (по умолчанию): `sqlite+aiosqlite:///./tournaments.db`
  - PostgreSQL: `postgresql+asyncpg://user:password@localhost:5432/chess_bot`
- `LOG_LEVEL` — минимальный уровень логирования.

### Флаги поведения

- `AUTO_ADVANCE_TO_NEXT_ROUND` — автопереход к следующему туру (`true/false`).
- `MODERATE_RESULTS` — модерация результатов организатором (`true/false`).

> Примечание: флаги `AUTO_ADVANCE_TO_NEXT_ROUND` и `MODERATE_RESULTS` уже подготовлены в `.env.example`, как часть текущих допущений проекта.

## 4. Уровни логирования

Логгер настраивается переменной `LOG_LEVEL`.

Поддерживаемые уровни (в порядке от наиболее подробного к наименее):

- `TRACE`
- `DEBUG`
- `INFO`
- `SUCCESS`
- `WARNING`
- `ERROR`
- `CRITICAL`

Рекомендуемые значения:

- локальная разработка: `DEBUG`;
- прод/стейджинг: `INFO` или `WARNING`.

## 5. Команды запуска и обслуживания

### Установка зависимостей

```bash
pip install -e .[dev]
```

### Миграции БД

```bash
alembic upgrade head
```

Откат на 1 миграцию:

```bash
alembic downgrade -1
```

Посмотреть текущую ревизию:

```bash
alembic current
```

### Запуск бота

```bash
python -m bot.main
```

### Тесты и проверки качества

```bash
pytest
ruff check .
mypy src
```

## 6. Доступные команды в Telegram

## Пользовательские команды

- `/start` — приветствие и краткая справка.
- `/rules` — правила турнира.
- `/schedule` — расписание/текущее состояние.
- `/my_next` — ближайшая партия игрока.
- `/my_score` — текущие очки игрока.
- `/standings` — турнирная таблица.
- `/report <round> <result>` — отправка результата.
  - Примеры:
    - `/report 1 1-0`
    - `/report 2 0-1`
    - `/report 3 0.5-0.5`
    - `/report 3 1/2-1/2`

## Команды организатора

- `/organizer` — меню/подсказка по орг-командам.
- `/add_player <telegram_id|@username> <имя>` — добавить игрока.
- `/disqualify <player_id|@username>` — дисквалифицировать игрока.
- `/tables` — список столов.
- `/add_table <номер> <локация>` — добавить стол.
- `/remove_table <номер>` — удалить стол.
- `/set_rules <текст>` — задать текст правил.
- `/start_tournament <rounds_count>` — запуск турнира и установка числа туров.
- `/next_round` — сгенерировать следующий тур.
- `/round <n>` — показать конкретный тур.
- `/approve_result <game_id>` — подтвердить результат при модерации.
- `/finish_tournament` — завершить турнир.

## 7. Минимальный сценарий проверки после запуска

1. Организатор выполняет `/start_tournament 5`.
2. Добавляет игроков `/add_player ...` (минимум 4).
3. Добавляет столы через `/add_table ...`.
4. Генерирует тур `/next_round`.
5. Игроки отправляют `/report <round> <result>`.
6. При необходимости организатор подтверждает `/approve_result <game_id>`.
7. Проверяется `/standings`, затем `/finish_tournament`.

## 8. Допущения и правила домена

1. **Модерация результатов включена по умолчанию**:
   - первый репорт помечается как pending;
   - совпадающий репорт соперника подтверждает результат автоматически;
   - конфликтующие репорты эскалируются организатору.
2. **Автопереход к следующему туру по умолчанию выключен**.
3. **BYE-партия** не требует репорта игрока.
4. Нельзя генерировать новый тур, пока предыдущий не завершен.
5. Поддерживаемые форматы результата: `1-0`, `0-1`, `0.5-0.5`, `1/2-1/2`.

## 9. Tie-break правила

Сортировка таблицы выполняется строго в порядке:

1. **Points**
2. **Buchholz**
3. **Sonneborn-Berger**
4. **Median Buchholz**
5. **Player ID (ASC)** — технический детерминирующий tie-break.
