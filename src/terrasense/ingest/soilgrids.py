"""Extract SoilGrids 2.0 (250 m, Interrupted Goode Homolosine) windows covering Nigeria.

The window is read from ISRIC's public VRTs on the native grid: no reprojection,
no resampling, values unchanged (int16, mapped unit g/kg for sand/silt/clay;
divide by 10 for %). Pixels outside Nigeria are NOT removed here; the API
rejects non-Nigerian queries using the boundary polygon.

These are MODELLED predictions (quantile regression forest, WoSIS data stream 7),
not measurements, and must never be used as validation truth.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from terrasense.config import RAW_DIR
from terrasense.geo.boundary import nigeria
from terrasense.ingest.fetch import FetchRecord, _now, hash_file, write_manifest

BASE = "https://files.isric.org/soilgrids/latest/data"
PROPS = ("sand", "silt", "clay")
DEPTHS = ("0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm")
STATS = ("mean", "Q0.05", "Q0.5", "Q0.95")
OUT = RAW_DIR / "soilgrids"


def layer_name(prop: str, depth: str, stat: str) -> str:
    return f"{prop}_{depth}_{stat}"


def extract_one(prop: str, depth: str, stat: str, retries: int = 3) -> FetchRecord:
    name = layer_name(prop, depth, stat)
    url = f"{BASE}/{prop}/{name}.vrt"
    dst = OUT / f"{name}.tif"
    if dst.exists():
        md5, sha = hash_file(dst)
        return FetchRecord("soilgrids", dst.name, url, str(dst.relative_to(RAW_DIR.parent.parent)), dst.stat().st_size,
                           md5, sha, None, None, "cached", _now())
    for attempt in range(retries):
        try:
            with rasterio.Env(GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="3", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
                with rasterio.open(f"/vsicurl/{url}") as src:
                    hb = transform_bounds("EPSG:4326", src.crs, *nigeria().geometry.bounds, densify_pts=50)
                    win = from_bounds(*hb, src.transform).round_offsets().round_lengths()
                    arr = src.read(1, window=win)
                    prof = {"driver": "GTiff", "dtype": "int16", "count": 1, "height": arr.shape[0], "width": arr.shape[1],
                            "crs": src.crs, "transform": src.window_transform(win), "nodata": src.nodata,
                            "compress": "deflate", "predictor": 2, "tiled": True, "blockxsize": 512, "blockysize": 512}
                    tags = {k: v for k, v in src.tags().items() if k in ("Code_version", "Model", "WoSIS_version", "Outputs_version")}
            tmp = dst.with_suffix(".part.tif")
            with rasterio.open(tmp, "w", **prof) as out:
                out.write(arr, 1)
                out.update_tags(source_url=url, mapped_unit="g/kg", conversion_to_percent="divide by 10",
                                window=str(win), **tags)
            tmp.replace(dst)
            md5, sha = hash_file(dst)
            return FetchRecord("soilgrids", dst.name, url, str(dst.relative_to(RAW_DIR.parent.parent)), dst.stat().st_size,
                               md5, sha, None, None, "extracted_window", _now())
        except Exception as exc:  # network hiccups through the proxy
            if attempt == retries - 1:
                return FetchRecord("soilgrids", dst.name, url, str(dst), None, None, None, None, None,
                                   f"error: {type(exc).__name__}: {exc}", _now())
            time.sleep(10 * (attempt + 1))


def fetch_soilgrids(props=PROPS, depths=DEPTHS, stats=STATS, workers: int = 6) -> list[FetchRecord]:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(p, d, s) for p in props for d in depths for s in stats]
    recs = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(extract_one, *j): j for j in jobs}
        for f in as_completed(futs):
            r = f.result()
            print(f"{r.status:18s} {r.key}", flush=True)
            recs.append(r)
    write_manifest(recs)
    return recs


# ---------------------------------------------------------------- WCS path (server-side subset, ~5x faster)

WCS = "https://maps.isric.org/mapserv?map=/map/{prop}.map"
IGH_CRS_URI = "http://www.opengis.net/def/crs/EPSG/0/152160"
# Native-grid window covering Nigeria, identical to the VRT window (col 81031, row 27261, 5502 x 4282)
GRID = {"xmin": 308000, "xmax": 308000 + 5502 * 250, "ymin": 1545750 - 4282 * 250, "ymax": 1545750}
MASK_REF = "sand_0-5cm_Q0.5"     # VRT-extracted layer whose nodata mask restores WCS nodata


def _wcs_url(prop: str, name: str) -> str:
    g = GRID
    return (WCS.format(prop=prop) + "&SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage"
            f"&COVERAGEID={name}&FORMAT=image/tiff&SUBSET=X({g['xmin']},{g['xmax']})&SUBSET=Y({g['ymin']},{g['ymax']})"
            f"&SUBSETTINGCRS={IGH_CRS_URI}&OUTPUTCRS={IGH_CRS_URI}")


def extract_one_wcs(prop: str, depth: str, stat: str, retries: int = 3) -> FetchRecord:
    """Fetch via WCS; WCS encodes nodata as 0 without a tag, so nodata is restored from the
    VRT-extracted reference mask. Zeros outside that mask are counted and left as 0 (recorded
    in tags) rather than silently converted."""
    import numpy as np
    import requests

    from terrasense.ingest.fetch import USER_AGENT
    name = layer_name(prop, depth, stat)
    dst = OUT / f"{name}.tif"
    url = _wcs_url(prop, name)
    rel = lambda p: str(p.relative_to(RAW_DIR.parent.parent))
    if dst.exists():
        md5, sha = hash_file(dst)
        return FetchRecord("soilgrids", dst.name, url, rel(dst), dst.stat().st_size, md5, sha, None, None, "cached", _now())
    ref = OUT / f"{MASK_REF}.tif"
    if not ref.exists():
        raise FileNotFoundError(f"mask reference {ref} missing: run VRT extraction for {MASK_REF} first")
    with rasterio.open(ref) as r:
        ref_mask = r.read(1) == r.nodata
        prof = r.profile.copy()
        ref_tf = r.transform
    tmp_dl = OUT / f"{name}.wcs.part"
    for attempt in range(retries):
        try:
            with requests.get(url, timeout=600, stream=True, headers={"User-Agent": USER_AGENT}) as resp:
                resp.raise_for_status()
                if "tiff" not in resp.headers.get("content-type", ""):
                    raise ValueError(f"unexpected content-type {resp.headers.get('content-type')}: {resp.text[:200]}")
                with open(tmp_dl, "wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            with rasterio.open(tmp_dl) as w:
                arr = w.read(1)
                if w.transform != ref_tf or arr.shape != ref_mask.shape:
                    raise ValueError(f"WCS grid {w.transform} {arr.shape} != reference {ref_tf} {ref_mask.shape}")
            zero = arr == 0
            zeros_outside_mask = int((zero & ~ref_mask).sum())
            nonzero_inside_mask = int((~zero & ref_mask).sum())
            out = np.where(ref_mask & zero, np.int16(-32768), arr).astype("int16")
            tmp = dst.with_suffix(".part.tif")
            with rasterio.open(tmp, "w", **prof) as o:
                o.write(out, 1)
                o.update_tags(source_url=url, retrieval="WCS 2.0.1 GetCoverage, native grid", mapped_unit="g/kg",
                              conversion_to_percent="divide by 10", nodata_restored_from=f"{MASK_REF}.tif (VRT extract)",
                              zeros_outside_reference_mask=str(zeros_outside_mask),
                              nonzero_inside_reference_mask=str(nonzero_inside_mask),
                              Model="Quantile Regression Forests", Code_version="v2.0.0")
            tmp.replace(dst)
            tmp_dl.unlink()
            md5, sha = hash_file(dst)
            st = "extracted_wcs" if zeros_outside_mask == 0 and nonzero_inside_mask == 0 else \
                f"extracted_wcs_mask_mismatch(z_out={zeros_outside_mask},nz_in={nonzero_inside_mask})"
            return FetchRecord("soilgrids", dst.name, url, rel(dst), dst.stat().st_size, md5, sha, None, None, st, _now())
        except Exception as exc:
            if attempt == retries - 1:
                return FetchRecord("soilgrids", dst.name, url, str(dst), None, None, None, None, None,
                                   f"error: {type(exc).__name__}: {exc}", _now())
            time.sleep(10 * (attempt + 1))


def fetch_soilgrids_wcs(props=PROPS, depths=DEPTHS, stats=STATS, workers: int = 3) -> list[FetchRecord]:
    OUT.mkdir(parents=True, exist_ok=True)
    recs = [extract_one(*MASK_REF.split("_"))]          # reference mask via VRT (cached if present)
    jobs = [(p, d, s) for p in props for d in depths for s in stats if layer_name(p, d, s) != MASK_REF]
    with ThreadPoolExecutor(workers) as ex:
        for f in as_completed([ex.submit(extract_one_wcs, *j) for j in jobs]):
            r = f.result()
            print(f"{r.status:22s} {r.key}", flush=True)
            recs.append(r)
    write_manifest(recs)
    return recs
