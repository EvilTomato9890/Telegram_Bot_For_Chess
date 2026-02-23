CREATE TABLE tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'registration', 'ongoing', 'finished')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    telegram_user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('registered', 'active', 'withdrawn', 'banned')),
    score REAL NOT NULL DEFAULT 0,
    buchholz REAL NOT NULL DEFAULT 0,
    median_buchholz REAL NOT NULL DEFAULT 0,
    sonneborn_berger REAL NOT NULL DEFAULT 0,
    UNIQUE (tournament_id, telegram_user_id)
);

CREATE TABLE rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned', 'active', 'finished')),
    UNIQUE (tournament_id, number)
);

CREATE TABLE tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    UNIQUE (round_id, number)
);

CREATE TABLE seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    color TEXT NOT NULL CHECK (color IN ('white', 'black')),
    UNIQUE (table_id, color),
    UNIQUE (table_id, player_id)
);

CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    table_id INTEGER REFERENCES tables(id) ON DELETE SET NULL,
    white_player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
    black_player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE RESTRICT,
    result TEXT CHECK (result IS NULL OR result IN ('1-0', '0-1', '0.5-0.5', 'bye', 'forfeit')),
    CHECK (white_player_id != black_player_id)
);

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_user_id INTEGER NOT NULL,
    ticket_type TEXT NOT NULL CHECK (ticket_type IN ('arbitr', 'organizer')),
    status TEXT NOT NULL CHECK (status IN ('open', 'assigned', 'closed')),
    assignee_user_id INTEGER,
    game_id INTEGER REFERENCES games(id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    closed_by_user_id INTEGER,
    closed_at TEXT
);

CREATE INDEX idx_players_tournament_id ON players(tournament_id);
CREATE INDEX idx_rounds_tournament_id ON rounds(tournament_id);
CREATE INDEX idx_games_round_id ON games(round_id);
CREATE INDEX idx_tickets_author_user_id ON tickets(author_user_id);
CREATE INDEX idx_tickets_game_id ON tickets(game_id);
