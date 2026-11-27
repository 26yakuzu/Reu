"""Nigeria boundary checks (geoBoundaries gbOpen NGA ADM0/ADM1, GRID3 source, CC BY 4.0).

The authoritative polygon is loaded from data/raw/geoboundaries_nga. If it is
absent the caller gets BoundaryUnavailable — we never silently fall back to a
bounding box, because a box would accept points in Benin, Niger, Chad and
Cameroon.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely import contains_xy, prepare
from shapely.geometry.base import BaseGeometry

from terrasense.config import RAW_DIR

ADM0_PATH = RAW_DIR / "geoboundaries_nga" / "geoBoundaries-NGA-ADM0.geojson"
ADM1_PATH = RAW_DIR / "geoboundaries_nga" / "geoBoundaries-NGA-ADM1.geojson"


class BoundaryUnavailable(RuntimeError):
    """Raised when the Nigeria boundary file has not been fetched."""


@dataclass(frozen=True)
class Boundary:
    geometry: BaseGeometry          # EPSG:4326
    states: gpd.GeoDataFrame | None
    source: str

    def contains(self, lon, lat) -> np.ndarray:
        lon = np.asarray(lon, dtype=float)
        lat = np.asarray(lat, dtype=float)
        ok = valid_lonlat(lon, lat)
        out = np.zeros(lon.shape, dtype=bool)
        out[ok] = contains_xy(self.geometry, lon[ok], lat[ok])
        return out

    def state_of(self, lon: float, lat: float) -> str | None:
        if self.states is None:
            return None
        hit = self.states[self.states.contains(gpd.points_from_xy([lon], [lat])[0])]
        return None if hit.empty else str(hit.iloc[0]["shapeName"])


def valid_lonlat(lon, lat) -> np.ndarray:
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    return np.isfinite(lon) & np.isfinite(lat) & (np.abs(lon) <= 180) & (np.abs(lat) <= 90)


def boundary_from_files(adm0: Path, adm1: Path | None = None) -> Boundary:
    if not adm0.exists():
        raise BoundaryUnavailable(f"{adm0} missing — run: python -I scripts/fetch.py --only geoboundaries_nga")
    g0 = gpd.read_file(adm0)
    if g0.crs is None or g0.crs.to_epsg() != 4326:
        g0 = g0.to_crs(4326)
    geom = g0.geometry.union_all()
    prepare(geom)
    states = None
    if adm1 is not None and adm1.exists():
        states = gpd.read_file(adm1).to_crs(4326)[["shapeName", "shapeISO", "geometry"]]
    return Boundary(geom, states, source=str(adm0.name))


@lru_cache(maxsize=1)
def nigeria() -> Boundary:
    return boundary_from_files(ADM0_PATH, ADM1_PATH)
