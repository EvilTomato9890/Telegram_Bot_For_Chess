# Telegram_Bot_For_Chess

Telegram bot for chess tournament in MIPT.

## Project layout

- `bot/` — application factory and runtime bootstrap.
- `domain/` — domain entities/value objects (reserved for expansion).
- `services/` — business service contracts.
- `repositories/` — persistence adapters (reserved for expansion).
- `handlers/` — telegram command/update handlers (reserved for expansion).
- `keyboards/` — telegram keyboard builders (reserved for expansion).
- `infra/` — infrastructure concerns (`config`, `logging`).
- `tests/` — automated tests.

## Установка и запуск

### 1) Установка зависимостей

Рекомендуется Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pytest
```

Проект использует стандартную библиотеку Python; для запуска тестов достаточно установить `pytest`.

### 2) Подготовка `.env`

Создайте `.env` в корне проекта (рядом с `main.py`) и заполните переменные:

```env
TOKEN=1234567890:AAExampleTelegramBotToken1234567890
DB_URL=sqlite:///data/tournament.db
ADMIN_IDS=111111111,222222222
ARBITRS_IDS=333333333,444444444
TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
AUDIT_LOG_PATH=logs/audit.log
```

Описание переменных:

- `TOKEN` — токен Telegram-бота от `@BotFather`.
- `DB_URL` — строка подключения к БД.
- `ADMIN_IDS` — ID администраторов через запятую.
- `ARBITRS_IDS` — ID арбитров через запятую.
- `TIMEZONE` — timezone в формате IANA.
- `LOG_LEVEL` — уровень логирования.
- `AUDIT_LOG_PATH` — путь к файлу аудита.

### 3) Инициализация БД и миграций

Начальные миграции находятся в `repositories/migrations/`.

Для SQLite:

```bash
mkdir -p data
python -m repositories.schema.init_db sqlite:///data/tournament.db
```

Если используется другая БД, укажите соответствующий `DB_URL` и выполните инициализацию с ним.

### 4) Запуск бота

```bash
python main.py
```

После запуска бот начинает принимать команды в Telegram.

## Примеры значений переменных

- `TOKEN`: `1234567890:AAExampleTelegramBotToken1234567890`
- `ADMIN_IDS`: `111111111,222222222`
- `ARBITRS_IDS`: `333333333,444444444`
- `TIMEZONE`: `Europe/Moscow` (также допустимы, например, `UTC`, `Asia/Yekaterinburg`)

## Сценарии использования

### Сценарий 1: от регистрации до старта турнира

1. Администратор создаёт турнир в статусе `draft`.
2. Администратор открывает регистрацию (переход в `registration`).
3. Игроки регистрируются в турнир.
4. Администратор проверяет список участников и закрывает регистрацию.
5. Администратор запускает турнир (переход в `ongoing`) и генерирует первый тур.

### Сценарий 2: проведение тура и фиксация результатов

1. В текущем туре формируются пары игроков.
2. Игрок отправляет результат своей партии (например, `1-0` или `0.5-0.5`).
3. Соперник подтверждает результат **или** результат подтверждает арбитр/админ.
4. При конфликте арбитр/админ делает override результата с обязательной причиной.
5. После фиксации всех партий рассчитывается таблица и подготавливается следующий тур.

### Сценарий 3: завершение турнира и публикация итогов

1. После последнего тура администратор/арбитр проверяет, что все результаты зафиксированы.
2. Турнир переводится из `ongoing` в `finished`.
3. Бот публикует итоговую таблицу (место, очки, дополнительные показатели — если предусмотрены логикой).
4. Изменение результатов и дальнейшие переходы статуса становятся недоступны.

## Допущения и известные ограничения

### Допущения

- Жизненный цикл турнира строго линейный: `draft -> registration -> ongoing -> finished`.
- Команды валидируются по текущему статусу турнира, запрещённые операции не меняют состояние.
- Форматы результатов ограничены набором: `1-0`, `0-1`, `0.5-0.5`, `bye`, `forfeit`.
- Override подтверждённого результата доступен только арбитру/админу и требует логирования причины.

### Известные ограничения

- После перехода в `finished` любые изменения результатов и статусов запрещены.
- Настройка турнира после начала ограничена или недоступна (в зависимости от команды).
- Некорректные форматы результата (например, `1:0` или `draw`) отклоняются.

Полный нормативный перечень ограничений и инвариантов — в [`docs/assumptions.md`](docs/assumptions.md).
