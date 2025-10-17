"""Window-based analytics helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from pyproj import Geod

from .. import crud, models

GEOD = Geod(ellps="WGS84")


class StatisticsService:
    """Compute aggregates over track windows."""

    def build_dataframe(self, points: Iterable[models.Point]) -> pd.DataFrame:
        data = [
            {
                "time": point.t,
                "lat": point.lat,
                "lon": point.lon,
                "sog_mps": point.sog_mps,
                "cog_deg": point.cog_deg,
            }
            for point in points
        ]
        if not data:
            return pd.DataFrame(columns=["time", "lat", "lon", "sog_mps", "cog_deg"])
        df = pd.DataFrame(data)
        df.sort_values("time", inplace=True)
        return df

    def compute_window(
        self,
        session,
        boat: models.Boat,
        t0: datetime,
        t1: datetime,
        ref: str,
        leg_mark_id: int | None = None,
    ) -> tuple[pd.DataFrame, dict[str, float]]:
        points = crud.list_points(session, boat.id, t0, t1)
        df = self.build_dataframe(points)
        if df.empty:
            return df, {
                "avg_sog": 0.0,
                "avg_vmg": 0.0,
                "avg_heading": 0.0,
                "heading_std": 0.0,
                "distance_sailed": 0.0,
                "height_gain": 0.0,
            }

        ref_dir = self._resolve_reference_direction(boat, df, ref, leg_mark_id)

        sog = df["sog_mps"].fillna(method="ffill").fillna(method="bfill").to_numpy()
        heading = df["cog_deg"].fillna(method="ffill").fillna(method="bfill")
        vmg = self._vmg(sog, heading.to_numpy(), ref_dir)

        avg_heading, heading_std = self._heading_stats(heading)
        metrics = {
            "avg_sog": float(np.nanmean(sog)),
            "avg_vmg": float(np.nanmean(vmg)),
            "avg_heading": avg_heading,
            "heading_std": float(heading_std),
            "distance_sailed": self._distance(df),
            "height_gain": self._height_gain(df, ref_dir),
        }
        return df, metrics

    @staticmethod
    def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        azimuth, _, _ = GEOD.inv(lon1, lat1, lon2, lat2)
        return (azimuth + 360.0) % 360.0

    def _resolve_reference_direction(
        self,
        boat: models.Boat,
        df: pd.DataFrame,
        ref: str,
        leg_mark_id: int | None,
    ) -> float:
        if ref == "twd":
            if boat.race.twd_deg is None:
                raise ValueError("Race does not have a TWD configured")
            return boat.race.twd_deg

        marks: Sequence[models.Mark] = sorted(boat.race.marks, key=lambda m: m.order_idx)
        if leg_mark_id is not None:
            mark = next((m for m in marks if m.id == leg_mark_id), None)
            if mark is None:
                raise ValueError("Invalid mark id")
        elif marks:
            mark = marks[0]
        else:
            raise ValueError("No marks defined for race")
        return self._bearing(df.iloc[0]["lat"], df.iloc[0]["lon"], mark.lat, mark.lon)

    @staticmethod
    def _vmg(sog: np.ndarray, heading: np.ndarray, ref_dir: float) -> np.ndarray:
        delta = np.radians((heading - ref_dir + 540.0) % 360.0 - 180.0)
        return sog * np.cos(delta)

    @staticmethod
    def _heading_stats(heading: pd.Series) -> tuple[float, float]:
        radians_series = np.deg2rad(heading.dropna())
        if radians_series.empty:
            return 0.0, 0.0
        sin_sum = np.sin(radians_series).mean()
        cos_sum = np.cos(radians_series).mean()
        mean_angle = (np.degrees(np.arctan2(sin_sum, cos_sum)) + 360.0) % 360.0
        angular_std = np.sqrt(-2 * np.log(np.hypot(sin_sum, cos_sum))) * 180.0 / np.pi
        return mean_angle, float(angular_std)

    @staticmethod
    def _height_gain(df: pd.DataFrame, ref_dir: float) -> float:
        if df.empty:
            return 0.0
        lat = np.deg2rad(df["lat"].values)
        lon = np.deg2rad(df["lon"].values)
        x = np.cos(lat) * np.cos(lon)
        y = np.cos(lat) * np.sin(lon)
        z = np.sin(lat)
        lat0, lon0 = lat[0], lon[0]
        x0 = np.cos(lat0) * np.cos(lon0)
        y0 = np.cos(lat0) * np.sin(lon0)
        z0 = np.sin(lat0)
        east = np.array([-np.sin(lon0), np.cos(lon0), 0.0])
        north = np.array(
            [-np.sin(lat0) * np.cos(lon0), -np.sin(lat0) * np.sin(lon0), np.cos(lat0)]
        )
        local_vectors = np.column_stack((x - x0, y - y0, z - z0))
        east_component = local_vectors @ east
        north_component = local_vectors @ north
        angle = np.radians(ref_dir)
        across = -north_component * np.sin(angle) + east_component * np.cos(angle)
        return float(across[-1] - across[0])

    @staticmethod
    def _distance(df: pd.DataFrame) -> float:
        if len(df) < 2:
            return 0.0
        total = 0.0
        for idx in range(len(df) - 1):
            _, _, distance = GEOD.inv(
                df.iloc[idx]["lon"],
                df.iloc[idx]["lat"],
                df.iloc[idx + 1]["lon"],
                df.iloc[idx + 1]["lat"],
            )
            total += distance
        return float(total)
