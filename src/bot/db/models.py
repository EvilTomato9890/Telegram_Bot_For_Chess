"""ORM entities for tournaments, players and pairings."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""


class Tournament(Base):
    """Tournament aggregate root with metadata and rounds."""

    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    rounds_total: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    players: Mapped[list[Player]] = relationship(back_populates="tournament", cascade="all, delete-orphan")


class Player(Base):
    """Tournament player with rating and optional tie-break cache fields."""

    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("tournament_id", "telegram_id", name="uq_player_tg_in_tour"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), nullable=False)
    telegram_id: Mapped[int] = mapped_column(Integer, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, default=1200, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    tournament: Mapped[Tournament] = relationship(back_populates="players")
