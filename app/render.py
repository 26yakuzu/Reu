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


@lru_cache(maxsize=16)
def overlay(layer_id: str, max_px: int = 1400):
    """Return (png_bytes, [[south, west], [north, east]]) or None."""
    layer = next(l for l in RASTER_LAYERS if l.id == layer_id)
    if not layer.path.exists():
        return None
    with rasterio.open(layer.path) as src:
        scale = max(src.width, src.height) / max_px
        w, h = max(1, int(src.width / max(scale, 1))), max(1, int(src.height / max(scale, 1)))
        tr, tw, th = calculate_default_transform(src.crs, "EPSG:3857", src.width, src.height, *src.bounds, dst_width=w, dst_height=h)
        dst = np.full((th, tw), src.nodata if src.nodata is not None else 0, dtype=np.uint8)
        reproject(rasterio.band(src, 1), dst, dst_transform=tr, dst_crs="EPSG:3857", resampling=Resampling.nearest,
                  dst_nodata=src.nodata)
        nodata = src.nodata
    rgba = np.zeros((*dst.shape, 4), dtype=np.uint8)
    pal = _palette(layer_id)
    if pal:
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
