"""CRS helpers. Distances/areas must be computed in a projected CRS, not degrees."""
from __future__ import annotations

from pyproj import CRS

WGS84 = CRS.from_epsg(4326)


def utm_for(lon: float, lat: float) -> CRS:
    """UTM zone CRS for a point. Nigeria spans zones 31N-33N."""
    zone = int((lon + 180) // 6) + 1
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def require_crs(crs, what: str) -> CRS:
    if crs is None:
        raise ValueError(f"{what}: dataset has no CRS — refusing to guess")
    return CRS.from_user_input(crs)


def is_geographic(crs) -> bool:
    return CRS.from_user_input(crs).is_geographic
