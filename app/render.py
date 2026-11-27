"""Display-only raster renderings (Web Mercator PNG overlays).

Values shown in panels always come from the native-resolution rasters via the
API/engine; these images are only for visual context on the map.
"""
from __future__ import annotations

import io
from functools import lru_cache

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.warp import Resampling, calculate_default_transform, reproject

from terrasense.geo.layers import RASTER_LAYERS

EO4F_COLORS = {1: (117, 168, 255), 2: (254, 95, 103), 3: (150, 134, 112), 4: (255, 228, 126), 5: (68, 225, 144), 6: (46, 149, 68)}
HAD_LC_COLORS = {1: (162, 70, 24), 2: (227, 26, 28), 3: (33, 159, 69), 4: (185, 233, 29), 5: (47, 215, 181), 6: (48, 54, 234)}
FLOOD_COLOR = {1: (20, 82, 217)}
PERM_COLOR = {1: (0, 0, 120)}


def _palette(layer_id: str):
    if layer_id.startswith("eo4forest"):
        return EO4F_COLORS
    if layer_id == "hadejia_landcover_2022":
        return HAD_LC_COLORS
    if "perm_water" in layer_id:
        return PERM_COLOR
    if "extent" in layer_id:
        return FLOOD_COLOR
    return None


def _ramp(t: np.ndarray, lo: tuple, hi: tuple) -> np.ndarray:
    t = np.clip(t, 0, 1)[..., None]
    return (np.array(lo) * (1 - t) + np.array(hi) * t).astype(np.uint8)


def _extra_path(layer_id: str):
    from terrasense.config import RAW_DIR
    from terrasense.geo.layers import current_dir
    return {"wofs_maxfreq_display": current_dir() / "wofs_maxfreq_display.tif",
            "soilgrids_sand_0-5cm_Q0.5": RAW_DIR / "soilgrids" / "sand_0-5cm_Q0.5.tif",
            "soilgrids_clay_0-5cm_Q0.5": RAW_DIR / "soilgrids" / "clay_0-5cm_Q0.5.tif"}.get(layer_id)


EXTRA_LAYERS = {"wofs_maxfreq_display": "WOfS water frequency 1984–2025 (display, 480 m block max)",
                "soilgrids_sand_0-5cm_Q0.5": "SoilGrids sand 0–5 cm, median (MODELLED, 250 m)",
                "soilgrids_clay_0-5cm_Q0.5": "SoilGrids clay 0–5 cm, median (MODELLED, 250 m)"}


@lru_cache(maxsize=16)
def overlay(layer_id: str, max_px: int = 1400):
    """Return (png_bytes, [[south, west], [north, east]]) or None."""
    layer = next((l for l in RASTER_LAYERS if l.id == layer_id), None)
    path = layer.path if layer else _extra_path(layer_id)
    if path is None or not path.exists():
        return None
    with rasterio.open(path) as src:
        scale = max(src.width, src.height) / max_px
        w, h = max(1, int(src.width / max(scale, 1))), max(1, int(src.height / max(scale, 1)))
        tr, tw, th = calculate_default_transform(src.crs, "EPSG:3857", src.width, src.height, *src.bounds, dst_width=w, dst_height=h)
        dtype = np.int16 if src.dtypes[0] == "int16" else np.uint8
        dst = np.full((th, tw), src.nodata if src.nodata is not None else 0, dtype=dtype)
        reproject(rasterio.band(src, 1), dst, dst_transform=tr, dst_crs="EPSG:3857", resampling=Resampling.nearest,
                  dst_nodata=src.nodata)
        nodata = src.nodata
    rgba = np.zeros((*dst.shape, 4), dtype=np.uint8)
    pal = _palette(layer_id) if layer else None
    if layer_id == "wofs_maxfreq_display":
        m = (dst != 255) & (dst > 0)
        rgba[..., :3] = _ramp(dst / 100.0, (170, 220, 255), (8, 48, 160))
        rgba[..., 3] = np.where(m, 210, 0)
    elif layer_id.startswith("soilgrids_"):
        m = dst != nodata
        rgba[..., :3] = _ramp(dst / 1000.0, (250, 240, 200), (140, 70, 20)) if "sand" in layer_id else \
            _ramp(dst / 600.0, (240, 240, 250), (120, 40, 120))
        rgba[..., 3] = np.where(m, 170, 0)
    elif pal:
        for v, rgb in pal.items():
            m = dst == v
            rgba[m, :3] = rgb
            rgba[m, 3] = 190
    else:  # frequency count (1..n) -> yellow-to-red ramp
        n = layer.n_scenes or 12
        m = (dst > 0) & (dst != (nodata if nodata is not None else 255))
        t = np.clip(dst / n, 0, 1)
        rgba[..., 0] = 255
        rgba[..., 1] = (230 * (1 - t)).astype(np.uint8)
        rgba[..., 2] = 40
        rgba[..., 3] = np.where(m, 200, 0)
    left, top = tr.c, tr.f
    right, bottom = left + tr.a * tw, top + tr.e * th
    to_ll = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    west, south = to_ll.transform(left, bottom)
    east, north = to_ll.transform(right, top)
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
    return buf.getvalue(), [[south, west], [north, east]]
