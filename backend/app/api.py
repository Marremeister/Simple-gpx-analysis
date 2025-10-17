"""FastAPI router wiring all service layers together."""
from __future__ import annotations

import io
import json
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import get_session
from .services import gpx as gpx_service
from .services import statistics as stats_service

router = APIRouter()


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from exc


@router.post("/race", response_model=schemas.RaceRead)
def create_race(payload: schemas.RaceCreate, session=Depends(get_session)):
    race = crud.create_race(session, payload)
    return schemas.RaceRead.model_validate(race)


@router.get("/race", response_model=list[schemas.RaceRead])
def list_races(session=Depends(get_session)):
    races = crud.list_races(session)
    return [schemas.RaceRead.model_validate(race) for race in races]


@router.post("/race/{race_id}/marks", response_model=list[schemas.MarkRead])
def create_marks(race_id: int, payload: list[schemas.MarkCreate], session=Depends(get_session)):
    marks = crud.create_marks(session, race_id, payload)
    return [schemas.MarkRead.model_validate(mark) for mark in marks]


@router.post("/boats", response_model=schemas.BoatRead)
def register_boat(payload: schemas.BoatCreate, session=Depends(get_session)):
    boat = crud.create_boat(session, payload)
    return schemas.BoatRead.model_validate(boat)


@router.get("/boats", response_model=list[schemas.BoatRead])
def list_boats(raceId: int | None = None, session=Depends(get_session)):
    boats = crud.list_boats(session, race_id=raceId)
    return [schemas.BoatRead.model_validate(boat) for boat in boats]


@router.post("/boats/{boat_id}/offset", response_model=schemas.BoatRead)
def update_boat_offset(boat_id: int, payload: schemas.BoatOffsetUpdate, session=Depends(get_session)):
    try:
        boat = crud.update_boat_offset(session, boat_id, payload.seconds)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return schemas.BoatRead.model_validate(boat)


@router.post("/uploads", response_model=list[schemas.UploadResult])
async def upload_tracks(
    race_id: int = Form(...),
    files: list[UploadFile] = File(...),
    boat_metadata: str | None = Form(None),
    session: Session = Depends(get_session),
):
    race = session.get(models.Race, race_id)
    if race is None:
        raise HTTPException(status_code=404, detail="Race not found")

    metadata: list[dict[str, str]] = []
    if boat_metadata:
        try:
            metadata = json.loads(boat_metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid boat_metadata JSON") from exc

    results: list[schemas.UploadResult] = []

    for index, file in enumerate(files):
        raw_bytes = await file.read()
        try:
            df = gpx_service.parse_gpx_to_points(raw_bytes)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse {file.filename}: {exc}") from exc

        meta = metadata[index] if index < len(metadata) else {}
        payload = schemas.BoatCreate(
            race_id=race_id,
            sail_no=meta.get("sail_no", file.filename or f"Boat {index + 1}"),
            label_color=meta.get("label_color", "#1f77b4"),
        )
        boat = crud.create_boat(session, payload)

        points = gpx_service.dataframe_to_points(df)
        crud.insert_points(session, boat.id, points)
        events = gpx_service.detect_events(df)
        crud.replace_events(session, boat.id, events)

        results.append(schemas.UploadResult(boat_id=boat.id, sail_no=boat.sail_no))

    return results


@router.get("/tracks", response_model=list[schemas.TrackResponse])
def get_tracks(
    boats: list[int] = [],
    t0: str | None = None,
    t1: str | None = None,
    downsample: str = "1s",
    session=Depends(get_session),
):
    t0_dt = _parse_time(t0)
    t1_dt = _parse_time(t1)
    if downsample not in {"1s", "5s"}:
        raise HTTPException(status_code=400, detail="Unsupported downsample interval")
    step = 1 if downsample == "1s" else 5

    responses: list[schemas.TrackResponse] = []
    for boat_id in boats:
        points = crud.list_points(session, boat_id, t0_dt, t1_dt)
        filtered = points[::step] if step > 1 else points
        responses.append(
            schemas.TrackResponse(
                boat_id=boat_id,
                points=[schemas.PointRead.model_validate(point) for point in filtered],
            )
        )
    return responses


def _compute_stats(session: Session, boats: list[int], t0: str, t1: str, ref: str, legId: int | None):
    if ref not in {"twd", "mark"}:
        raise HTTPException(status_code=400, detail="ref must be 'twd' or 'mark'")

    t0_dt = _parse_time(t0)
    t1_dt = _parse_time(t1)
    if t0_dt is None or t1_dt is None:
        raise HTTPException(status_code=400, detail="t0 and t1 are required")

    responses: list[schemas.StatsResponse] = []
    for boat_id in boats:
        boat = session.get(models.Boat, boat_id)
        if boat is None:
            raise HTTPException(status_code=404, detail=f"Boat {boat_id} not found")
        try:
            df, metrics = stats_service.compute_window_statistics(session, boat, t0_dt, t1_dt, ref, legId)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        responses.append(
            schemas.StatsResponse(
                boat_id=boat_id,
                avg_sog=metrics["avg_sog"],
                avg_vmg=metrics["avg_vmg"],
                avg_heading=metrics["avg_heading"],
                heading_std=metrics["heading_std"],
                distance_sailed=metrics["distance_sailed"],
                height_gain=metrics["height_gain"],
                tack_count=crud.count_events(session, boat_id, t0_dt, t1_dt, models.EventType.TACK),
                gybe_count=crud.count_events(session, boat_id, t0_dt, t1_dt, models.EventType.GYBE),
            )
        )
    return responses


@router.get("/stats", response_model=list[schemas.StatsResponse])
def get_stats(
    boats: list[int],
    t0: str,
    t1: str,
    ref: str = "twd",
    legId: int | None = None,
    session: Session = Depends(get_session),
):
    return _compute_stats(session, boats, t0, t1, ref, legId)


@router.get("/compare", response_model=list[schemas.CompareResponse])
def compare_boats(
    reference: int,
    targets: list[int],
    t0: str,
    t1: str,
    ref: str = "twd",
    legId: int | None = None,
    session: Session = Depends(get_session),
):
    stats = _compute_stats(session, [reference, *targets], t0, t1, ref, legId)
    lookup = {stat.boat_id: stat for stat in stats}
    responses: list[schemas.CompareResponse] = []
    ref_stat = lookup[reference]
    for target in targets:
        target_stat = lookup[target]
        responses.append(
            schemas.CompareResponse(
                reference_boat=reference,
                target_boat=target,
                delta_vmg=target_stat.avg_vmg - ref_stat.avg_vmg,
                delta_height=target_stat.height_gain - ref_stat.height_gain,
                delta_sog=target_stat.avg_sog - ref_stat.avg_sog,
            )
        )
    return responses


@router.get("/events", response_model=list[schemas.EventRead])
def list_events(
    boats: list[int],
    t0: str | None = None,
    t1: str | None = None,
    type: models.EventType | None = None,
    session: Session = Depends(get_session),
):
    events = crud.list_events(session, boats, _parse_time(t0), _parse_time(t1), type)
    return [schemas.EventRead.model_validate(event) for event in events]


@router.get("/export/csv")
def export_csv(
    boats: list[int],
    t0: str,
    t1: str,
    ref: str = "twd",
    session: Session = Depends(get_session),
):
    stats = _compute_stats(session, boats, t0, t1, ref, None)
    df = pd.DataFrame([stat.model_dump() for stat in stats])
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return StreamingResponse(
        csv_buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=window_stats.csv"},
    )


@router.get("/export/snapshot.png")
def export_snapshot(state: str):
    # A full map renderer is beyond the MVP backend scope, return informative placeholder.
    detail = {
        "message": "Snapshot rendering is not implemented in the backend. Use the frontend map export instead.",
        "state": state,
    }
    return JSONResponse(status_code=501, content=detail)
