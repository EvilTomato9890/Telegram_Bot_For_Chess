"""ORM entities for tournaments, players, rounds, games and tables."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from bot.domain.enums import GameResult, GameStatus, PlayerStatus, RoundStatus, TournamentStatus

if TYPE_CHECKING:
    from collections.abc import Sequence


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""


class Tournament(Base):
    """Tournament aggregate root with metadata and rounds."""

    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[TournamentStatus] = mapped_column(
        Enum(TournamentStatus, native_enum=False),
        default=TournamentStatus.DRAFT,
        nullable=False,
    )
    rounds_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rules_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    players: Mapped[list[Player]] = relationship(back_populates="tournament", cascade="all, delete-orphan")
    rounds: Mapped[list[Round]] = relationship(back_populates="tournament", cascade="all, delete-orphan")


class Player(Base):
    """Tournament player state and tie-break values."""

    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("tournament_id", "telegram_id", name="uq_player_tg_in_tour"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[PlayerStatus] = mapped_column(
        Enum(PlayerStatus, native_enum=False),
        default=PlayerStatus.REGISTERED,
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    had_bye: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    color_history: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    buchholz: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sonneborn_berger: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    median_buchholz: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    tournament: Mapped[Tournament] = relationship(back_populates="players")
    white_games: Mapped[list[Game]] = relationship(foreign_keys="Game.white_player_id", back_populates="white_player")
    black_games: Mapped[list[Game]] = relationship(foreign_keys="Game.black_player_id", back_populates="black_player")


class Round(Base):
    """Tournament round metadata and timing."""

    __tablename__ = "rounds"
    __table_args__ = (UniqueConstraint("tournament_id", "number", name="uq_round_number_in_tour"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[RoundStatus] = mapped_column(
        Enum(RoundStatus, native_enum=False),
        default=RoundStatus.SCHEDULED,
        nullable=False,
    )

    tournament: Mapped[Tournament] = relationship(back_populates="rounds")
    games: Mapped[list[Game]] = relationship(back_populates="round", cascade="all, delete-orphan")


class Table(Base):
    """Physical or virtual board/table details."""

    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    games: Mapped[list[Game]] = relationship(back_populates="table")


class Game(Base):
    """Single game within a round."""

    __tablename__ = "games"
    __table_args__ = (UniqueConstraint("round_id", "board_no", name="uq_game_board_in_round"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    board_no: Mapped[int] = mapped_column(Integer, nullable=False)
    table_id: Mapped[int | None] = mapped_column(ForeignKey("tables.id", ondelete="SET NULL"), nullable=True)
    seat: Mapped[str | None] = mapped_column(String(32), nullable=True)
    white_player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), nullable=False)
    black_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="RESTRICT"), nullable=True)
    result: Mapped[GameResult | None] = mapped_column(Enum(GameResult, native_enum=False), nullable=True)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus, native_enum=False),
        default=GameStatus.PENDING,
        nullable=False,
    )
    reported_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    round: Mapped[Round] = relationship(back_populates="games")
    table: Mapped[Table | None] = relationship(back_populates="games")
    white_player: Mapped[Player] = relationship(foreign_keys=[white_player_id], back_populates="white_games")
    black_player: Mapped[Player | None] = relationship(foreign_keys=[black_player_id], back_populates="black_games")
