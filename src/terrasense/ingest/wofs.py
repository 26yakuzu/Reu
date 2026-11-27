"""Digital Earth Africa WOfS all-time summary (Landsat, 30 m, EPSG:6933) tiles over Nigeria.

Downloads count_wet + count_clear per tile (frequency = count_wet / count_clear,
per DE Africa specification) plus the STAC item, and verifies each file against
the publisher's .sha1 list. Licence: CC BY 4.0 (docs.digitalearthafrica.org,
Landsat WOfS specification).
"""
from __future__ import annotations

import hashlib
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from pyproj import Transformer
from shapely import transform as shp_transform
from shapely.geometry import box

from terrasense.config import RAW_DIR
from terrasense.geo.boundary import nigeria
from terrasense.ingest.fetch import USER_AGENT, FetchRecord, _now, hash_file, write_manifest

BUCKET = "https://deafrica-services.s3.af-south-1.amazonaws.com"
PRODUCT = "wofs_ls_summary_alltime"
VERSION = "1-0-0"
PERIOD = "1984--P42Y"            # 1984-01-01 .. 2025-12-31 (verified from STAC item)
TILE_M = 96_000                  # 3200 px x 30 m
X0, Y0 = 181, 76                 # tile index offsets: x_min=(ix-181)*96 km, y_max=(iy-76)*96 km
BANDS = ("count_wet", "count_clear")
OUT = RAW_DIR / "deafrica_wofs"


def tile_bounds(ix: int, iy: int) -> tuple[float, float, float, float]:
    return ((ix - X0) * TILE_M, (iy - Y0 - 1) * TILE_M, (ix - X0 + 1) * TILE_M, (iy - Y0) * TILE_M)


def tile_of(x: float, y: float) -> tuple[int, int]:
    return math.floor(x / TILE_M) + X0, math.floor(y / TILE_M) + Y0 + 1


def nigeria_tiles() -> list[tuple[int, int]]:
    t = Transformer.from_crs(4326, 6933, always_xy=True)
    g = shp_transform(nigeria().geometry, lambda xy: __import__("numpy").column_stack(t.transform(xy[:, 0], xy[:, 1])))
    minx, miny, maxx, maxy = g.bounds
    (ix0, iy0), (ix1, iy1) = tile_of(minx, miny), tile_of(maxx, maxy)
    return [(ix, iy) for ix in range(ix0, ix1 + 1) for iy in range(iy0, iy1 + 1) if box(*tile_bounds(ix, iy)).intersects(g)]


def _prefix(ix: int, iy: int) -> str:
    return f"{PRODUCT}/{VERSION}/x{ix:03d}/y{iy:03d}/{PERIOD}/{PRODUCT}_x{ix:03d}y{iy:03d}_{PERIOD}"


def fetch_tile(ix: int, iy: int, session: requests.Session) -> list[FetchRecord]:
    pre = _prefix(ix, iy)
    d = OUT / f"x{ix:03d}y{iy:03d}"
    d.mkdir(parents=True, exist_ok=True)
    r = session.get(f"{BUCKET}/{pre}.sha1", timeout=60)
    if r.status_code == 404:
        return [FetchRecord("deafrica_wofs", f"x{ix:03d}y{iy:03d}", f"{BUCKET}/{pre}.sha1", str(d), None, None, None,
                            None, None, "no_tile_published", _now())]
    r.raise_for_status()
    sums = {line.split()[1]: line.split()[0] for line in r.text.strip().splitlines()}
    recs = []
    for suffix in ["_count_wet.tif", "_count_clear.tif", ".stac-item.json"]:
        name = pre.rsplit("/", 1)[1] + suffix
        dest = d / name
        url = f"{BUCKET}/{pre}{suffix}"
        expected = sums.get(name)
        status = "cached"
        if not dest.exists():
            resp = session.get(url, timeout=120)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            status = "downloaded"
        sha1 = hashlib.sha1(dest.read_bytes()).hexdigest()
        ok = None if expected is None else sha1 == expected
        if ok is False:
            dest.replace(dest.with_suffix(dest.suffix + ".checksum_mismatch"))
            status = "rejected_checksum_mismatch"
        md5, sha256 = hash_file(dest) if dest.exists() else (None, None)
        recs.append(FetchRecord("deafrica_wofs", f"x{ix:03d}y{iy:03d}/{name}", url,
                                str(dest.relative_to(RAW_DIR.parent.parent)), dest.stat().st_size if dest.exists() else None,
                                md5, sha256, f"sha1:{expected}" if expected else None, ok, status, _now()))
    return recs


def fetch_wofs(workers: int = 6) -> list[FetchRecord]:
    tiles = nigeria_tiles()
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    recs: list[FetchRecord] = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch_tile, ix, iy, s): (ix, iy) for ix, iy in tiles}
        for f in as_completed(futs):
            try:
                rs = f.result()
            except Exception as exc:
                ix, iy = futs[f]
                rs = [FetchRecord("deafrica_wofs", f"x{ix:03d}y{iy:03d}", "", "", None, None, None, None, None,
                                  f"error: {exc}", _now())]
            recs += rs
    write_manifest(recs)
    return recs
