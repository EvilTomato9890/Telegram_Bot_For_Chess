CREATE TABLE tournaments (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL CHECK (status IN ('draft', 'registration', 'ongoing', 'finished')),
    number_of_rounds INTEGER NOT NULL DEFAULT 0 CHECK (number_of_rounds >= 0),
    current_round INTEGER NOT NULL DEFAULT 0 CHECK (current_round >= 0),
    rules_text TEXT NOT NULL DEFAULT '',
    prepared INTEGER NOT NULL DEFAULT 0 CHECK (prepared IN (0, 1)),
    pending_pairing_payload TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    full_name TEXT NOT NULL,
    rating INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('active', 'disqualified')),
    score REAL NOT NULL DEFAULT 0,
    buchholz REAL NOT NULL DEFAULT 0,
    median_buchholz REAL NOT NULL DEFAULT 0,
    sonneborn_berger REAL NOT NULL DEFAULT 0,
    had_bye INTEGER NOT NULL DEFAULT 0 CHECK (had_bye IN (0, 1)),
    current_board INTEGER,
    seat_hint TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('generated', 'ongoing', 'closed')),
    starts_at TEXT,
    window_end_at TEXT,
    generated_at TEXT NOT NULL,
    closed_at TEXT
);

CREATE TABLE tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL UNIQUE,
    location TEXT NOT NULL,
    place_hint TEXT
);

CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    board_number INTEGER NOT NULL,
    white_player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
    black_player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
    result TEXT CHECK (result IS NULL OR result IN ('1-0', '0-1', '0.5-0.5', 'bye', 'forfeit')),
    result_source TEXT,
    is_bye INTEGER NOT NULL DEFAULT 0 CHECK (is_bye IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (is_bye = 1 AND white_player_id = black_player_id)
        OR (is_bye = 0 AND white_player_id <> black_player_id)
    )
);

CREATE TABLE game_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    reporter_player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    reported_result TEXT NOT NULL CHECK (reported_result IN ('1-0', '0-1', '0.5-0.5', 'bye', 'forfeit')),
    created_at TEXT NOT NULL,
    UNIQUE (game_id, reporter_player_id)
);

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK (type IN ('arbitr', 'organizer')),
    author_telegram_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'assigned', 'closed')),
    assignee_telegram_id INTEGER,
    game_id INTEGER REFERENCES games(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    closed_by_telegram_id INTEGER
);

CREATE TABLE role_grants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('player', 'arbitrator', 'organizer')),
    source TEXT NOT NULL CHECK (source IN ('grant', 'revoke')),
    created_at TEXT NOT NULL
);

CREATE TABLE undo_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_telegram_id INTEGER NOT NULL,
    action_name TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    restored_at TEXT
);

CREATE INDEX idx_players_telegram_id ON players(telegram_id);
CREATE INDEX idx_games_round_id ON games(round_id);
CREATE INDEX idx_tickets_status_assignee ON tickets(status, assignee_telegram_id);
CREATE INDEX idx_game_reports_game_id ON game_reports(game_id);
