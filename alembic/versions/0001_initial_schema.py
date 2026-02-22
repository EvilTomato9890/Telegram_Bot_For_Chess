"""Initial schema for tournaments, rounds and pairings."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False, unique=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.Enum("DRAFT", "ACTIVE", "FINISHED", "CANCELED", name="tournamentstatus", native_enum=False), nullable=False),
        sa.Column("rounds_count", sa.Integer(), nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rules_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column("status", sa.Enum("REGISTERED", "ACTIVE", "WITHDRAWN", "DISQUALIFIED", name="playerstatus", native_enum=False), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("had_bye", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("color_history", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("buchholz", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sonneborn_berger", sa.Float(), nullable=False, server_default="0"),
        sa.Column("median_buchholz", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tournament_id", "telegram_id", name="uq_player_tg_in_tour"),
    )

    op.create_table(
        "rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tournament_id", sa.Integer(), sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.Enum("SCHEDULED", "ACTIVE", "FINISHED", name="roundstatus", native_enum=False), nullable=False),
        sa.UniqueConstraint("tournament_id", "number", name="uq_round_number_in_tour"),
    )

    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("board_no", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), sa.ForeignKey("tables.id", ondelete="SET NULL"), nullable=True),
        sa.Column("white_player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("black_player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("result", sa.Enum("WHITE_WIN", "BLACK_WIN", "DRAW", "BYE", name="gameresult", native_enum=False), nullable=True),
        sa.Column("status", sa.Enum("PENDING", "IN_PROGRESS", "FINISHED", "CANCELED", name="gamestatus", native_enum=False), nullable=False),
        sa.Column("reported_by", sa.Integer(), nullable=True),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("round_id", "board_no", name="uq_game_board_in_round"),
    )


def downgrade() -> None:
    op.drop_table("games")
    op.drop_table("rounds")
    op.drop_table("players")
    op.drop_table("tournaments")
    op.drop_table("tables")
