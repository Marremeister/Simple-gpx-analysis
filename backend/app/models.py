"""SQLAlchemy models for the race analysis domain."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class EventType(str, Enum):
    """Event type enumeration."""

    TACK = "tack"
    GYBE = "gybe"
    ROUNDING = "rounding"


class Race(Base):
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    twd_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    tws_kt: Mapped[float | None] = mapped_column(Float, nullable=True)

    marks: Mapped[list["Mark"]] = relationship(back_populates="race", cascade="all, delete-orphan")
    boats: Mapped[list["Boat"]] = relationship(back_populates="race", cascade="all, delete-orphan")


class Mark(Base):
    __tablename__ = "marks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    order_idx: Mapped[int] = mapped_column(Integer)
    gate_group: Mapped[str | None] = mapped_column(String(50), nullable=True)

    race: Mapped[Race] = relationship(back_populates="marks")


class Boat(Base):
    __tablename__ = "boats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"))
    sail_no: Mapped[str] = mapped_column(String(50))
    label_color: Mapped[str] = mapped_column(String(20))
    offset_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    race: Mapped[Race] = relationship(back_populates="boats")
    points: Mapped[list["Point"]] = relationship(back_populates="boat", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="boat", cascade="all, delete-orphan")


class Point(Base):
    __tablename__ = "points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    boat_id: Mapped[int] = mapped_column(ForeignKey("boats.id", ondelete="CASCADE"), index=True)
    t: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    sog_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    cog_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    src_rate_hz: Mapped[float | None] = mapped_column(Float, nullable=True)

    boat: Mapped[Boat] = relationship(back_populates="points")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    boat_id: Mapped[int] = mapped_column(ForeignKey("boats.id", ondelete="CASCADE"), index=True)
    t: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    type: Mapped[EventType] = mapped_column(SAEnum(EventType))
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    boat: Mapped[Boat] = relationship(back_populates="events")
