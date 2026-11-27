"""Stage 2 preprocessing: raw -> data/processed (versioned, reproducible).

* Rasters are re-encoded losslessly as uint8 COG (values preserved exactly; nodata
  made explicit). Native CRS and resolution are kept — nothing is resampled.
* Vectors are written as GeoParquet in EPSG:4326 with QC flags; rejected rows are
  kept in the file with `qc_reject_reason` so the decision is auditable.
"""
from __future__ import annotations

import hashlib
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.shutil import copy as rio_copy
from rasterio.windows import Window

from terrasense.config import MANIFEST_DIR, PROCESSED_DIR, RAW_DIR
from terrasense.geo.boundary import nigeria

PREP_VERSION = "2026.11.27-2"

H = RAW_DIR / "hadejia_flood" / "extracted"
E = RAW_DIR / "eo4forest_lagos_ogun" / "extracted"

# name -> (source path, mapping function float->uint8, nodata_out)
RASTERS = {
    "eo4forest_landcover_2023-12": (E / "ClassificationMaps" / "AOI0_2023-12.tif", "classes", 0),
    "hadejia_flood_extent_2020": (H / "Flood_Extent_Layers_RF_S1_and_PS/2020/Combined_Flood_Extent_PS_S1_2020.tif", "binary0", 255),
    "hadejia_flood_extent_2022": (H / "Flood_Extent_Layers_RF_S1_and_PS/2022/Combined_Flood_Extent_PS_S1_2022.tif", "binary0", 255),
    "hadejia_flood_freq_2020": (H / "Flood_Frequency_Layers/Flood_Frequency_PS_S1_Combine_2020_Mask_Cropland.tif", "frac_n11", 255),
    "hadejia_flood_freq_2022": (H / "Flood_Frequency_Layers/Flood_Frequency_PS_S1_Combine_2022_Mask_Cropland.tif", "frac_n12", 255),
    "hadejia_perm_water_2022": (H / "Perm_Water_Layer/Permanenet_Water_2022.tif", "presence", 0),
    "hadejia_landcover_2022": (H / "Land_Cover_Layers/Land_Cover_Layer_2022.tif", "classes", 0),
}


def _map_block(a: np.ndarray, nodata_in, mode: str) -> np.ndarray:
    nd = np.zeros(a.shape, bool) if nodata_in is None else (a == nodata_in)
    nd |= ~np.isfinite(a)
    if mode == "classes":       # integer class codes, 0 = no data per publisher legend
        out = np.where(nd, 0, a).astype(np.uint8)
    elif mode == "binary0":     # publisher nodata=0 coincides with 'not flooded' -> keep 0/1, no nodata
        out = np.where(nd, 0, a).astype(np.uint8)
    elif mode.startswith("frac_n"):  # fraction of N scenes flagged flooded -> integer count of scenes
        n = int(mode[6:])
        out = np.where(nd, 255, np.rint(a * n)).astype(np.uint8)
    elif mode == "presence":    # valid pixel = permanent water; nodata elsewhere
        out = np.where(nd, 0, 1).astype(np.uint8)
    else:
        raise ValueError(mode)
    return out


def to_cog(src_path: Path, dst: Path, mode: str, nodata_out: int) -> dict:
    tmp = dst.with_suffix(".tmp.tif")
    with rasterio.open(src_path) as src:
        prof = src.profile.copy()
        prof.update(driver="GTiff", dtype="uint8", nodata=nodata_out, compress="deflate", tiled=True,
                    blockxsize=512, blockysize=512, count=1, BIGTIFF="IF_SAFER")
        with rasterio.open(tmp, "w", **prof) as dst_ds:
            for row in range(0, src.height, 2048):
                h = min(2048, src.height - row)
                win = Window(0, row, src.width, h)
                dst_ds.write(_map_block(src.read(1, window=win), src.nodata, mode), 1, window=win)
        meta = {"crs": str(src.crs), "res": list(src.res), "shape": [src.height, src.width],
                "bounds": list(src.bounds), "source": str(src_path.relative_to(RAW_DIR.parent.parent))}
    rio_copy(tmp, dst, driver="COG", compress="DEFLATE")
    tmp.unlink()
    return meta


def prepare_vectors(out: Path) -> dict:
    b = nigeria()
    res = {}
    # Boundary (display copies; analysis uses the raw full-resolution polygon)
    for lvl in ("ADM0", "ADM1"):
        g = gpd.read_file(RAW_DIR / "geoboundaries_nga" / f"geoBoundaries-NGA-{lvl}.geojson")
        g.geometry = g.geometry.simplify(0.005, preserve_topology=True)
        p = out / f"nga_{lvl.lower()}_display.geojson"
        g.to_file(p, driver="GeoJSON")
        res[p.name] = {"rows": len(g), "note": "simplified 0.005 deg for display only"}

    # Soils4Africa Nigeria field sites
    df = pd.read_csv(RAW_DIR / "s4a_field" / "s4a_field_data.csv", low_memory=False)
    ng = df[df.country_code == "NG"].copy()
    ng["survey_date"] = pd.to_datetime(ng.survey_date, format="%Y/%m/%d", errors="coerce")
    ng["qc_reject_reason"] = np.where(b.contains(ng.longitude, ng.latitude), "", "outside_nigeria")
    g = gpd.GeoDataFrame(ng, geometry=gpd.points_from_xy(ng.longitude, ng.latitude), crs=4326)
    g.to_parquet(out / "s4a_field_nga.parquet")
    res["s4a_field_nga.parquet"] = {"rows": len(g), "rejected": int((g.qc_reject_reason != "").sum())}

    # Wetland ground control points (class labels; no observation date in source)
    gcp = pd.read_excel(RAW_DIR / "wetland_south_ng/extracted/Wetland Data/Ground_control_points_1.xlsx").iloc[:, :4].dropna()
    gcp.columns = ["class_code", "class_name", "lon", "lat"]
    dec = gcp.lon.astype(str).str.split(".").str[1].fillna("").str.len()
    reason = np.where(~b.contains(gcp.lon, gcp.lat), "outside_nigeria",
                      np.where(dec < 3, "coordinate_precision_lt_3_decimals",
                               np.where(gcp.duplicated(["lon", "lat"], keep="first"), "duplicate_coordinate", "")))
    gcp["coord_decimals"] = dec
    gcp["qc_reject_reason"] = reason
    g = gpd.GeoDataFrame(gcp, geometry=gpd.points_from_xy(gcp.lon, gcp.lat), crs=4326)
    g.to_parquet(out / "wetland_gcp_south_ng.parquet")
    res["wetland_gcp_south_ng.parquet"] = {"rows": len(g), "rejected": pd.Series(reason).value_counts().to_dict()}

    # HydroBASINS: keep full (unclipped) polygons that touch Nigeria + Africa-wide topology table
    for lev in ("06", "08"):
        p = RAW_DIR / "hydrobasins_af" / "extracted" / f"hybas_af_lev{lev}_v1c.shp"
        if not p.exists():
            continue
        allb = gpd.read_file(p)
        hit = allb[allb.intersects(b.geometry)].copy()
        hit.to_parquet(out / f"hybas_lev{lev}_nga.parquet")
        pd.DataFrame(allb.drop(columns="geometry")).to_parquet(out / f"hybas_lev{lev}_af_topology.parquet")
        res[f"hybas_lev{lev}_nga.parquet"] = {"rows": len(hit), "note": "unclipped polygons; topology table keeps upstream context"}

    # Coverage outlines
    aoi = gpd.read_file(E / "AOI_boundaries" / "AOI0_OugunLagos.shp").to_crs(4326)[["geometry"]]
    aoi["layer"] = "eo4forest_aoi"
    had = gpd.read_file(H / "Study_Area_Shp" / "Hadejia_boundary_FAO_UTM_32N.shp").to_crs(4326)[["geometry"]]
    had["layer"] = "hadejia_study_area"
    cov = pd.concat([aoi, had], ignore_index=True)
    cov.to_file(out / "coverage_outlines.geojson", driver="GeoJSON")
    res["coverage_outlines.geojson"] = {"rows": len(cov)}
    return res


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def prepare_all(skip_rasters: bool = False) -> Path:
    out = PROCESSED_DIR / PREP_VERSION
    out.mkdir(parents=True, exist_ok=True)
    vec = prepare_vectors(out)
    ras = {}
    if not skip_rasters:
        for name, (src, mode, nd) in RASTERS.items():
            if not src.exists():
                ras[name] = {"status": "missing_raw", "path": str(src)}
                continue
            dst = out / f"{name}.tif"
            if not dst.exists():
                ras[name] = to_cog(src, dst, mode, nd)
            else:
                with rasterio.open(dst) as r:
                    ras[name] = {"crs": str(r.crs), "res": list(r.res), "shape": [r.height, r.width], "bounds": list(r.bounds),
                                 "source": str(src.relative_to(RAW_DIR.parent.parent)), "reused_cached_output": True}
            ras[name]["encoding"] = mode
    from terrasense.ingest.wofs import OUT as WOFS_DIR
    if WOFS_DIR.exists() and not skip_rasters:
        ras["wofs_maxfreq_display"] = build_wofs_display(out)
    files = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()}
    manifest = {"prep_version": PREP_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "vectors": vec, "rasters": ras, "files": files}
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    mp = MANIFEST_DIR / f"processed_{PREP_VERSION}.json"
    mp.write_text(json.dumps(manifest, indent=2, default=str))
    (PROCESSED_DIR / "CURRENT").write_text(PREP_VERSION)
    return mp


def build_wofs_display(out: Path, block: int = 16) -> dict:
    """Display-only mosaic: max WOfS frequency (%) in 16x16-pixel blocks (480 m), EPSG:6933.

    Max (not mean) keeps narrow rivers visible. NEVER used for point values.
    """
    from terrasense.ingest.wofs import OUT as WOFS_DIR, TILE_M, nigeria_tiles, tile_bounds, PRODUCT, PERIOD
    tiles = nigeria_tiles()
    if not tiles:
        return {"status": "no_tiles"}
    xs = [tile_bounds(*t) for t in tiles]
    left, bottom = min(b[0] for b in xs), min(b[1] for b in xs)
    right, top = max(b[2] for b in xs), max(b[3] for b in xs)
    res = 30 * block
    W, Hh = int((right - left) / res), int((top - bottom) / res)
    mos = np.full((Hh, W), 255, np.uint8)
    n = 0
    for ix, iy in tiles:
        stem = WOFS_DIR / f"x{ix:03d}y{iy:03d}" / f"{PRODUCT}_x{ix:03d}y{iy:03d}_{PERIOD}"
        pw, pc = Path(f"{stem}_count_wet.tif"), Path(f"{stem}_count_clear.tif")
        if not (pw.exists() and pc.exists()):
            continue
        with rasterio.open(pw) as a, rasterio.open(pc) as b:
            wet, clear = a.read(1).astype(np.float32), b.read(1).astype(np.float32)
        valid = (clear > 0) & (wet >= 0)
        f = np.where(valid, wet / np.where(clear > 0, clear, 1), np.nan)
        k = f.shape[0] // block
        blk = f[:k * block, :k * block].reshape(k, block, k, block)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN blocks are expected (no clear obs)
            mx = np.nanmax(blk, axis=(1, 3))
        cell = np.where(np.isnan(mx), 255, np.rint(mx * 100)).astype(np.uint8)
        tl, _, _, tt = tile_bounds(ix, iy)
        c0, r0 = int((tl - left) / res), int((top - tt) / res)
        mos[r0:r0 + k, c0:c0 + k] = cell
        n += 1
    dst = out / "wofs_maxfreq_display.tif"
    with rasterio.open(dst, "w", driver="GTiff", height=Hh, width=W, count=1, dtype="uint8", crs="EPSG:6933",
                       transform=rasterio.transform.from_origin(left, top, res, res), nodata=255,
                       compress="deflate", tiled=True) as ds:
        ds.write(mos, 1)
        ds.update_tags(purpose="display only; block max of WOfS frequency (%), 480 m",
                       source="deafrica wofs_ls_summary_alltime 1-0-0 1984--P42Y")
    return {"tiles_used": n, "res_m": res, "shape": [Hh, W], "note": "display only"}
