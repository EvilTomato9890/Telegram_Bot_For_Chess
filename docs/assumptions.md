# Допущения и инварианты

## 1. Один турнир
- В БД хранится только один активный турнир (`tournaments.id = 1`).
- Команды работают в single-tournament режиме.

## 2. Статусы
- `tournament`: `draft -> registration -> ongoing -> finished`.
- `round`: `generated -> ongoing -> closed`.
- `player`: `active | disqualified`.
- `ticket`: `open | assigned | closed`.

## 3. Тай-брейки
Сортировка:
1. `score DESC`
2. `buchholz DESC`
3. `median_buchholz DESC`
4. `sonneborn_berger DESC`
5. `rating DESC`
6. `full_name ASC`

Формулы:
- `Buchholz`: сумма очков соперников.
- `Median Buchholz`: `Buchholz` без min/max при 3+ соперниках.
- `Sonneborn-Berger`: сумма `(очки в партии * итоговые очки соперника)`.

## 4. Результаты игр
Канон:
- `1-0`, `0-1`, `0.5-0.5`, `bye`, `forfeit`.

Нормализация `/report`:
- `White|white|Белые|1-0` -> `1-0`
- `Black|black|Черные|0-1` -> `0-1`
- `Draw|draw|Ничья|0.5-0.5` -> `0.5-0.5`

Допущение:
- `forfeit` интерпретируется как победа белых.

## 5. Швейцарские пары
- Основа сортировки при генерации: `score desc`, `rating desc`, `player_id asc`.
- Повторные встречи запрещены строго.
- Если строгая генерация невозможна: требуется `/confirm_next_round`.
- Третий подряд одинаковый цвет penalize (мягко).
- Bye назначается игроку без прошлых bye, если возможно.

## 6. Undo
- `/undo_last_action` доступен только организатору.
- Откат применяет последний snapshot, сделанный до mutating-команд организатора.
- Один вызов = один шаг назад.

