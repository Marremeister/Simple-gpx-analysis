"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Sequence

from pydantic import BaseModel, Field

from .models import EventType


class RaceCreate(BaseModel):
    name: str
    start_time: datetime
    twd_deg: float | None = Field(default=None, description="True wind direction")
    tws_kt: float | None = Field(default=None, description="True wind speed")


class RaceRead(RaceCreate):
    id: int

    class Config:
        from_attributes = True


class MarkCreate(BaseModel):
    name: str
    lat: float
    lon: float
    order_idx: int
    gate_group: str | None = None


class MarkRead(MarkCreate):
    id: int

    class Config:
        from_attributes = True


class BoatCreate(BaseModel):
    race_id: int
    sail_no: str
    label_color: str


class BoatRead(BaseModel):
    id: int
    race_id: int
    sail_no: str
    label_color: str
    offset_seconds: float

    class Config:
        from_attributes = True


class BoatOffsetUpdate(BaseModel):
    seconds: float


class PointRead(BaseModel):
    t: datetime
    lat: float
    lon: float
    sog_mps: float | None = None
    cog_deg: float | None = None

    class Config:
        from_attributes = True


class TrackResponse(BaseModel):
    boat_id: int
    points: Sequence[PointRead]


class StatsResponse(BaseModel):
    boat_id: int
    avg_sog: float
    avg_vmg: float
    avg_heading: float
    heading_std: float
    distance_sailed: float
    height_gain: float
    tack_count: int
    gybe_count: int


class CompareResponse(BaseModel):
    reference_boat: int
    target_boat: int
    delta_vmg: float
    delta_height: float
    delta_sog: float


class EventRead(BaseModel):
    id: int
    boat_id: int
    t: datetime
    type: EventType
    meta: dict | None

    class Config:
        from_attributes = True


class UploadResult(BaseModel):
    boat_id: int
    sail_no: str


class CSVRow(BaseModel):
    boat_id: int
    metrics: dict[str, Any]


class ExportState(BaseModel):
    boats: Iterable[int]
    t0: datetime
    t1: datetime
    include_trails: bool = True
