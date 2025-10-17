"""Utility CRUD functions to keep routers compact."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import models, schemas


def create_race(session: Session, payload: schemas.RaceCreate) -> models.Race:
    race = models.Race(**payload.model_dump())
    session.add(race)
    session.flush()
    return race


def list_races(session: Session) -> Sequence[models.Race]:
    return session.scalars(select(models.Race).order_by(models.Race.start_time)).all()


def create_marks(session: Session, race_id: int, payloads: Iterable[schemas.MarkCreate]) -> list[models.Mark]:
    marks = [models.Mark(race_id=race_id, **payload.model_dump()) for payload in payloads]
    session.add_all(marks)
    session.flush()
    return marks


def create_boat(session: Session, payload: schemas.BoatCreate) -> models.Boat:
    boat = models.Boat(**payload.model_dump())
    session.add(boat)
    session.flush()
    return boat


def list_boats(session: Session, race_id: int | None = None) -> Sequence[models.Boat]:
    stmt = select(models.Boat)
    if race_id is not None:
        stmt = stmt.where(models.Boat.race_id == race_id)
    return session.scalars(stmt.order_by(models.Boat.sail_no)).all()


def update_boat_offset(session: Session, boat_id: int, seconds: float) -> models.Boat:
    boat = session.get(models.Boat, boat_id)
    if boat is None:
        raise ValueError("Boat not found")
    boat.offset_seconds = seconds
    session.add(boat)
    session.flush()
    return boat


def insert_points(session: Session, boat_id: int, points: list[models.Point]) -> None:
    for point in points:
        point.boat_id = boat_id
    session.add_all(points)


def delete_points(session: Session, boat_id: int) -> None:
    session.execute(delete(models.Point).where(models.Point.boat_id == boat_id))


def list_points(session: Session, boat_id: int, t0: datetime | None, t1: datetime | None) -> list[models.Point]:
    stmt = select(models.Point).where(models.Point.boat_id == boat_id)
    if t0 is not None:
        stmt = stmt.where(models.Point.t >= t0)
    if t1 is not None:
        stmt = stmt.where(models.Point.t <= t1)
    stmt = stmt.order_by(models.Point.t)
    return session.scalars(stmt).all()


def list_events(
    session: Session, boat_ids: Iterable[int], t0: datetime | None = None, t1: datetime | None = None, event_type: models.EventType | None = None
) -> list[models.Event]:
    stmt = select(models.Event).where(models.Event.boat_id.in_(list(boat_ids)))
    if t0 is not None:
        stmt = stmt.where(models.Event.t >= t0)
    if t1 is not None:
        stmt = stmt.where(models.Event.t <= t1)
    if event_type is not None:
        stmt = stmt.where(models.Event.type == event_type)
    stmt = stmt.order_by(models.Event.t)
    return session.scalars(stmt).all()


def replace_events(session: Session, boat_id: int, events: list[models.Event]) -> None:
    session.execute(delete(models.Event).where(models.Event.boat_id == boat_id))
    for event in events:
        event.boat_id = boat_id
    session.add_all(events)


def count_events(session: Session, boat_id: int, t0: datetime, t1: datetime, event_type: models.EventType) -> int:
    stmt = (
        select(func.count(models.Event.id))
        .where(models.Event.boat_id == boat_id)
        .where(models.Event.t >= t0)
        .where(models.Event.t <= t1)
        .where(models.Event.type == event_type)
    )
    return session.scalar(stmt) or 0
