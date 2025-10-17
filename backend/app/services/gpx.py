"""GPX parsing, resampling and feature extraction utilities."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import gpxpy
import gpxpy.gpx
import numpy as np
import pandas as pd
from pyproj import Geod

from .. import models

GEOD = Geod(ellps="WGS84")


@dataclass
class ProcessedTrack:
    """Container for processed track data."""

    boat: models.Boat
    dataframe: pd.DataFrame


def _read_gpx(file_like: BytesIO) -> gpxpy.gpx.GPX:
    file_like.seek(0)
    return gpxpy.parse(file_like)


def _extract_points(gpx: gpxpy.gpx.GPX) -> list[dict[str, float | datetime]]:
    points: list[dict[str, float | datetime]] = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if point.time is None:
                    continue
                points.append(
                    {
                        "time": point.time.replace(tzinfo=None),
                        "lat": point.latitude,
                        "lon": point.longitude,
                        "sog": point.speed if point.speed is not None else np.nan,
                    }
                )
    return points


def _resample(points: list[dict[str, float | datetime]]) -> pd.DataFrame:
    if not points:
        raise ValueError("GPX file contains no points with timestamps")

    df = pd.DataFrame(points).drop_duplicates(subset="time")
    df = df.sort_values("time").set_index("time")
    # Fill missing SOG values with NaN to compute later.
    df["sog"] = pd.to_numeric(df["sog"], errors="coerce")

    resampled = df.resample("1S").interpolate(method="time")
    resampled["src_rate_hz"] = 1.0
    resampled.reset_index(inplace=True)
    resampled.rename(columns={"index": "time"}, inplace=True)

    # Compute segment distances and derived metrics.
    lats = np.deg2rad(resampled["lat"].values)
    lons = np.deg2rad(resampled["lon"].values)
    lat1 = lats[:-1]
    lat2 = lats[1:]
    lon1 = lons[:-1]
    lon2 = lons[1:]

    # pyproj.Geod returns forward azimuth, back azimuth, distance.
    fwd_azimuth, _, distances = GEOD.inv(np.rad2deg(lon1), np.rad2deg(lat1), np.rad2deg(lon2), np.rad2deg(lat2))
    dt = np.diff(resampled["time"].values.astype("datetime64[s]").astype(np.int64))
    dt = dt.astype(float)
    dt[dt == 0] = 1.0

    sog = np.append(distances / dt, np.nan)
    cog = np.append((fwd_azimuth + 360.0) % 360.0, np.nan)

    resampled.loc[:-2, "sog_computed"] = sog[:-1]
    resampled.loc[:-2, "cog_raw"] = cog[:-1]

    resampled["sog_mps"] = resampled["sog"].fillna(resampled["sog_computed"])
    resampled["cog_deg"] = pd.Series(resampled["cog_raw"]).interpolate().fillna(method="bfill").fillna(method="ffill")
    resampled["cog_deg"] = resampled["cog_deg"].rolling(window=5, center=True, min_periods=1).median()

    resampled.drop(columns=["sog", "sog_computed", "cog_raw"], inplace=True, errors="ignore")
    return resampled


def parse_gpx_to_points(file_bytes: bytes) -> pd.DataFrame:
    """Parse a GPX file and return a resampled dataframe."""
    gpx = _read_gpx(BytesIO(file_bytes))
    points = _extract_points(gpx)
    return _resample(points)


def dataframe_to_points(df: pd.DataFrame) -> list[models.Point]:
    """Convert a dataframe to Point ORM objects."""
    points: list[models.Point] = []
    for row in df.itertuples(index=False):
        points.append(
            models.Point(
                t=pd.Timestamp(row.time).to_pydatetime(),
                lat=float(row.lat),
                lon=float(row.lon),
                sog_mps=float(row.sog_mps) if not pd.isna(row.sog_mps) else None,
                cog_deg=float(row.cog_deg) if not pd.isna(row.cog_deg) else None,
                src_rate_hz=float(row.src_rate_hz) if not pd.isna(row.src_rate_hz) else None,
            )
        )
    return points


def detect_events(df: pd.DataFrame) -> list[models.Event]:
    """Detect tacks and gybes with a simple heuristic."""
    events: list[models.Event] = []
    heading = df["cog_deg"].values
    sog = df["sog_mps"].values
    times = pd.to_datetime(df["time"]).to_pydatetime()

    window = 10
    for idx in range(window, len(df) - window):
        before = heading[idx - window]
        after = heading[idx + window]
        change = (after - before + 540) % 360 - 180
        local_sog = sog[max(0, idx - 3) : idx + 4]
        if np.isnan(change):
            continue
        if abs(change) >= 90 and np.nanmin(local_sog) <= np.nanmean(sog) * 0.8:
            event_type = models.EventType.TACK if change > 0 else models.EventType.GYBE
            events.append(
                models.Event(
                    t=times[idx],
                    type=event_type,
                    meta={"heading_change": float(change)},
                )
            )
    return events
