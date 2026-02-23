CREATE INDEX IF NOT EXISTS idx_role_grants_telegram_id ON role_grants(telegram_id);
CREATE INDEX IF NOT EXISTS idx_undo_snapshots_created_at ON undo_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_rounds_number ON rounds(number);
CREATE INDEX IF NOT EXISTS idx_games_players ON games(white_player_id, black_player_id);

