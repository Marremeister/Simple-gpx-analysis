"""REST API implemented with Flask blueprints."""
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Iterable

import pandas as pd
from flask import Blueprint, Response, jsonify, request
from pydantic import ValidationError

from .. import crud, models, schemas
from ..database import get_session
from ..services.gpx import GPXService
from ..services.statistics import StatisticsService

api_bp = Blueprint("api", __name__)

_gpx_service = GPXService()
_stats_service = StatisticsService()

COLOR_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid datetime: {value}") from exc


def _bad_request(message: str, detail: Any | None = None):
    payload = {"detail": message}
    if detail is not None:
        payload["errors"] = detail
    return jsonify(payload), 400


@api_bp.post("/race")
def create_race():
    data = request.get_json(silent=True) or {}
    try:
        payload = schemas.RaceCreate.model_validate(data)
    except ValidationError as exc:
        return _bad_request("Invalid race payload", exc.errors())

    with get_session() as session:
        race = crud.create_race(session, payload)
        return jsonify(schemas.RaceRead.model_validate(race).model_dump())


@api_bp.get("/race")
def list_races():
    with get_session() as session:
        races = crud.list_races(session)
        return jsonify([schemas.RaceRead.model_validate(race).model_dump() for race in races])


@api_bp.post("/race/<int:race_id>/marks")
def create_marks(race_id: int):
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return _bad_request("Payload must be a list of marks")
    try:
        payloads = [schemas.MarkCreate.model_validate(item) for item in data]
    except ValidationError as exc:
        return _bad_request("Invalid mark payload", exc.errors())

    with get_session() as session:
        marks = crud.create_marks(session, race_id, payloads)
        return jsonify([schemas.MarkRead.model_validate(mark).model_dump() for mark in marks])


@api_bp.post("/boats")
def register_boat():
    data = request.get_json(silent=True) or {}
    try:
        payload = schemas.BoatCreate.model_validate(data)
    except ValidationError as exc:
        return _bad_request("Invalid boat payload", exc.errors())

    with get_session() as session:
        boat = crud.create_boat(session, payload)
        return jsonify(schemas.BoatRead.model_validate(boat).model_dump())


@api_bp.get("/boats")
def list_boats():
    race_id = request.args.get("raceId", type=int)
    with get_session() as session:
        boats = crud.list_boats(session, race_id=race_id)
        return jsonify([schemas.BoatRead.model_validate(boat).model_dump() for boat in boats])


@api_bp.post("/boats/<int:boat_id>/offset")
def update_boat_offset(boat_id: int):
    data = request.get_json(silent=True) or {}
    try:
        payload = schemas.BoatOffsetUpdate.model_validate(data)
    except ValidationError as exc:
        return _bad_request("Invalid offset payload", exc.errors())

    with get_session() as session:
        try:
            boat = crud.update_boat_offset(session, boat_id, payload.seconds)
        except ValueError as exc:
            return _bad_request(str(exc))
        return jsonify(schemas.BoatRead.model_validate(boat).model_dump())


@api_bp.post("/uploads")
def upload_tracks():
    if "race_id" not in request.form:
        return _bad_request("race_id form field is required")
    try:
        race_id = int(request.form["race_id"])
    except ValueError:
        return _bad_request("race_id must be an integer")

    files = request.files.getlist("files")
    if not files:
        return _bad_request("No GPX files provided")

    metadata_raw = request.form.get("boat_metadata")
    metadata: list[dict[str, str]] = []
    if metadata_raw:
        try:
            decoded = json.loads(metadata_raw)
            if isinstance(decoded, list):
                metadata = decoded
            else:
                return _bad_request("boat_metadata must be a JSON list")
        except json.JSONDecodeError as exc:
            return _bad_request("Invalid boat_metadata JSON", str(exc))

    results: list[schemas.UploadResult] = []
    with get_session() as session:
        race = session.get(models.Race, race_id)
        if race is None:
            return _bad_request("Race not found")

        # Count existing boats to determine color index
        existing_boats_count = len(crud.list_boats(session, race_id=race_id))

        for index, storage in enumerate(files):
            raw_bytes = storage.read()
            try:
                df = _gpx_service.parse(raw_bytes)
            except Exception as exc:  # noqa: BLE001 - surface parsing issues to clients
                return _bad_request(f"Failed to parse {storage.filename}: {exc}")

            meta = metadata[index] if index < len(metadata) else {}
            # Assign color from palette, cycling if necessary
            color_index = (existing_boats_count + index) % len(COLOR_PALETTE)
            assigned_color = meta.get("label_color", COLOR_PALETTE[color_index])

            payload = schemas.BoatCreate(
                race_id=race_id,
                sail_no=meta.get("sail_no", storage.filename or f"Boat {index + 1}"),
                label_color=assigned_color,
            )
            boat = crud.create_boat(session, payload)

            points = _gpx_service.dataframe_to_points(df)
            crud.insert_points(session, boat.id, points)
            events = _gpx_service.detect_events(df)
            crud.replace_events(session, boat.id, events)

            results.append(schemas.UploadResult(boat_id=boat.id, sail_no=boat.sail_no))

    return jsonify([result.model_dump() for result in results])


@api_bp.get("/tracks")
def get_tracks():
    boat_ids = request.args.getlist("boats", type=int)
    t0 = request.args.get("t0")
    t1 = request.args.get("t1")
    downsample = request.args.get("downsample", "1s")
    if downsample not in {"1s", "5s"}:
        return _bad_request("Unsupported downsample interval")
    step = 1 if downsample == "1s" else 5

    try:
        t0_dt = _parse_time(t0)
        t1_dt = _parse_time(t1)
    except ValueError as exc:
        return _bad_request(str(exc))

    with get_session() as session:
        responses: list[schemas.TrackResponse] = []
        for boat_id in boat_ids:
            points = crud.list_points(session, boat_id, t0_dt, t1_dt)
            filtered = points[::step] if step > 1 else points
            responses.append(
                schemas.TrackResponse(
                    boat_id=boat_id,
                    points=[schemas.PointRead.model_validate(point) for point in filtered],
                )
            )
        return jsonify([resp.model_dump() for resp in responses])


def _compute_stats(
    session,
    boats: Iterable[int],
    t0: str,
    t1: str,
    ref: str,
    leg_id: int | None,
):
    if ref not in {"twd", "mark"}:
        raise ValueError("ref must be 'twd' or 'mark'")

    t0_dt = _parse_time(t0)
    t1_dt = _parse_time(t1)
    if t0_dt is None or t1_dt is None:
        raise ValueError("t0 and t1 are required")

    responses: list[schemas.StatsResponse] = []
    for boat_id in boats:
        boat = session.get(models.Boat, boat_id)
        if boat is None:
            raise ValueError(f"Boat {boat_id} not found")
        df, metrics = _stats_service.compute_window(session, boat, t0_dt, t1_dt, ref, leg_id)
        responses.append(
            schemas.StatsResponse(
                boat_id=boat_id,
                avg_sog=metrics["avg_sog"],
                avg_vmg=metrics["avg_vmg"],
                avg_heading=metrics["avg_heading"],
                heading_std=metrics["heading_std"],
                distance_sailed=metrics["distance_sailed"],
                height_gain=metrics["height_gain"],
                tack_count=crud.count_events(
                    session,
                    boat_id,
                    t0_dt,
                    t1_dt,
                    models.EventType.TACK,
                ),
                gybe_count=crud.count_events(
                    session,
                    boat_id,
                    t0_dt,
                    t1_dt,
                    models.EventType.GYBE,
                ),
            )
        )
    return responses


@api_bp.get("/stats")
def get_stats():
    boat_ids = request.args.getlist("boats", type=int)
    t0 = request.args.get("t0")
    t1 = request.args.get("t1")
    ref = request.args.get("ref", "twd")
    leg_id = request.args.get("legId", type=int)
    if not boat_ids:
        return _bad_request("boats query parameter is required")
    with get_session() as session:
        try:
            stats = _compute_stats(session, boat_ids, t0, t1, ref, leg_id)
        except ValueError as exc:
            return _bad_request(str(exc))
        return jsonify([item.model_dump() for item in stats])


@api_bp.get("/compare")
def compare_boats():
    reference = request.args.get("reference", type=int)
    targets = request.args.getlist("targets", type=int)
    t0 = request.args.get("t0")
    t1 = request.args.get("t1")
    ref = request.args.get("ref", "twd")
    leg_id = request.args.get("legId", type=int)
    if reference is None:
        return _bad_request("reference query parameter is required")

    with get_session() as session:
        try:
            stats = _compute_stats(session, [reference, *targets], t0, t1, ref, leg_id)
        except ValueError as exc:
            return _bad_request(str(exc))
        lookup = {item.boat_id: item for item in stats}
        ref_stat = lookup[reference]
        responses: list[schemas.CompareResponse] = []
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
        return jsonify([item.model_dump() for item in responses])


@api_bp.get("/events")
def list_events():
    boat_ids = request.args.getlist("boats", type=int)
    t0 = request.args.get("t0")
    t1 = request.args.get("t1")
    event_type = request.args.get("type")
    if not boat_ids:
        return jsonify([])
    try:
        t0_dt = _parse_time(t0)
        t1_dt = _parse_time(t1)
    except ValueError as exc:
        return _bad_request(str(exc))

    enum_value = None
    if event_type:
        try:
            enum_value = models.EventType(event_type)
        except ValueError:
            return _bad_request("Invalid event type")

    with get_session() as session:
        events = crud.list_events(session, boat_ids, t0_dt, t1_dt, enum_value)
        return jsonify([schemas.EventRead.model_validate(event).model_dump() for event in events])


@api_bp.get("/export/csv")
def export_csv():
    boat_ids = request.args.getlist("boats", type=int)
    t0 = request.args.get("t0")
    t1 = request.args.get("t1")
    ref = request.args.get("ref", "twd")
    if not boat_ids:
        return _bad_request("boats query parameter is required")

    with get_session() as session:
        try:
            stats = _compute_stats(session, boat_ids, t0, t1, ref, None)
        except ValueError as exc:
            return _bad_request(str(exc))
    df = pd.DataFrame([stat.model_dump() for stat in stats])
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    return Response(
        csv_buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=window_stats.csv"},
    )


@api_bp.get("/export/snapshot.png")
def export_snapshot():
    state = request.args.get("state")
    detail = {
        "message": "Snapshot rendering is not implemented in the backend. Use the frontend map export instead.",
        "state": state,
    }
    return jsonify(detail), 501