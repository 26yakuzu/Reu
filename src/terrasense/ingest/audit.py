"""Stage 1 audit: inspect what the raw files ACTUALLY contain.

Each auditor returns a dict of facts computed from the files on disk plus an
`eligibility` verdict per intended role. Nothing here is copied from the
project brief; every number is recomputed on each run.
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
from sklearn.neighbors import KDTree

from terrasense.config import RAW_DIR, load_registry
from terrasense.geo.boundary import Boundary, nigeria, valid_lonlat

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _missing(source_id: str, needed: list[str]) -> dict:
    return {"status": "not_fetched", "missing": needed,
            "fix": f"python -I scripts/fetch.py --only {source_id} --include-large && python -I scripts/extract.py"}


def _point_stats(lon, lat, b: Boundary) -> dict:
    lon, lat = np.asarray(lon, float), np.asarray(lat, float)
    valid = valid_lonlat(lon, lat)
    inside = b.contains(lon, lat)
    return {"n": int(lon.size), "invalid_coordinates": int((~valid).sum()),
            "inside_nigeria": int(inside.sum()), "outside_nigeria_valid": int((valid & ~inside).sum()),
            "bbox_valid_inside": [float(lon[inside].min()), float(lat[inside].min()),
                                  float(lon[inside].max()), float(lat[inside].max())] if inside.any() else None}


def _decimals(series: pd.Series) -> dict:
    d = series.astype(str).str.split(".").str[1].fillna("").str.len()
    return {int(k): int(v) for k, v in d.value_counts().sort_index().items()}


# --------------------------------------------------------------------------- sources

def audit_boundary() -> dict:
    p0 = RAW_DIR / "geoboundaries_nga" / "geoBoundaries-NGA-ADM0.geojson"
    p1 = RAW_DIR / "geoboundaries_nga" / "geoBoundaries-NGA-ADM1.geojson"
    if not p0.exists():
        return _missing("geoboundaries_nga", [str(p0)])
    g0, g1 = gpd.read_file(p0), gpd.read_file(p1)
    area = g0.to_crs("ESRI:102022").area.sum() / 1e6  # Africa Albers equal-area
    return {"status": "ok", "crs": str(g0.crs), "adm0_valid": bool(g0.is_valid.all()),
            "bounds": [round(float(x), 4) for x in g0.total_bounds], "area_km2": round(float(area)),
            "adm1_units": int(len(g1)), "adm1_names": sorted(g1.shapeName.tolist())}


def audit_s4a_field(b: Boundary) -> dict:
    p = RAW_DIR / "s4a_field" / "s4a_field_data.csv"
    if not p.exists():
        return _missing("s4a_field", [str(p)])
    df = pd.read_csv(p, low_memory=False)
    ng = df[df["country_code"] == "NG"].copy()
    stats = _point_stats(ng["longitude"], ng["latitude"], b)
    xy_match = bool(np.allclose(ng["X"], ng["longitude"]) and np.allclose(ng["Y"], ng["latitude"]))
    dates = pd.to_datetime(ng["survey_date"], format="%Y/%m/%d", errors="coerce")
    texture_cols = [c for c in df.columns if re.search(r"sand|silt|clay|texture", c, re.I)]
    counts = {c: ng[c].value_counts(dropna=False).head(10).rename(str).to_dict()
              for c in ["main_land_use", "bare_soil", "lndform", "slope_class", "depth_restriction_cause",
                        "srf_crust", "crsfrgab", "sign_of_erosion"]}
    states = None
    if b.states is not None:
        pts = gpd.GeoDataFrame(ng, geometry=gpd.points_from_xy(ng.longitude, ng.latitude), crs=4326)
        states = gpd.sjoin(pts, b.states, predicate="within")["shapeName"].value_counts().to_dict()
    return {"status": "ok", "rows_total": int(len(df)), "columns": int(df.shape[1]), "nigeria_rows": int(len(ng)),
            "unique_plot_codes": int(ng["plot_code"].nunique()), "points": stats, "X_Y_equal_lon_lat": xy_match,
            "coordinate_decimals": _decimals(ng["longitude"]),
            "survey_date_range": [str(dates.min().date()), str(dates.max().date())] if dates.notna().any() else None,
            "unparseable_dates": int(dates.isna().sum()),
            "texture_columns_present": texture_cols, "categorical_counts": counts, "sites_per_state": states,
            "eligibility": {
                "soil_texture_target": "NO — field file has no sand/silt/clay; lab release not downloadable",
                "surface_context_display": "YES — measured field description at plot, survey date shown",
                "visible_surface_labels": "LIMITED — bare_soil is Yes/No at plot level only (agricultural sites)"}}


def audit_ozoro() -> dict:
    p = RAW_DIR / "ozoro_texture" / "ozoro.docx"
    if not p.exists():
        return _missing("ozoro_texture", [str(p)])
    root = ET.fromstring(zipfile.ZipFile(p).read("word/document.xml"))
    tables = []
    for tbl in root.iter(W + "tbl"):
        rows = [["".join(t.text or "" for t in tc.iter(W + "t")).strip() for tc in tr.iter(W + "tc")]
                for tr in tbl.iter(W + "tr")]
        tables.append(rows)
    text = "".join(t.text or "" for t in root.iter(W + "t"))
    coord_hits = re.findall(r"\d{1,2}\s*°\s*\d{1,2}|latitude|longitude|GPS|UTM|northing|easting", text, re.I)
    tex = next((t for t in tables if t and "%Sandy" in t[0]), None)
    tex_summary = None
    if tex:
        data = [r for r in tex[1:] if r and r[0].isdigit()]
        pct = np.array([[float(r[5]), float(r[6]), float(r[7])] for r in data])
        sums = pct.sum(axis=1)
        tex_summary = {"header": tex[0], "data_rows": len(data),
                       "sum_pct_min": float(sums.min()), "sum_pct_max": float(sums.max()),
                       "rows_not_summing_to_100": int((np.abs(sums - 100) > 1).sum()),
                       "mean_sand_clay_silt_pct": [round(float(x), 1) for x in pct.mean(axis=0)],
                       "classes": pd.Series([r[8] for r in data]).value_counts().to_dict()}
    return {"status": "ok", "file_type": "docx (manuscript)", "tables": [(len(t), len(t[0]) if t else 0) for t in tables],
            "texture_table": tex_summary, "coordinate_mentions": coord_hits,
            "eligibility": {"soil_texture_target": "NO — 50 aggregated 'experiment' rows (not 750 samples), "
                                                  "no coordinates, jar-test method; cannot be georeferenced",
                            "context_display": "YES — area-level summary for Ozoro (Isoko North LGA), cite as such"}}


def audit_wetland(b: Boundary) -> dict:
    d = RAW_DIR / "wetland_south_ng" / "extracted" / "Wetland Data"
    if not d.exists():
        return _missing("wetland_south_ng", [str(d)])
    present = sorted(p.name for p in d.iterdir())
    gcp = pd.read_excel(d / "Ground_control_points_1.xlsx").iloc[:, :4].dropna()
    stats = _point_stats(gcp["Location_x"], gcp["Location_y"], b)
    dec = gcp["Location_x"].astype(str).str.split(".").str[1].fillna("").str.len()
    tfw = [float(x) for x in (d / "Wetlandmap.tfw").read_text().split()]
    return {"status": "ok", "files_present": present,
            "wetland_map_raster_present": (d / "Wetlandmap.tif").exists(),
            "wetland_map_vector_geometry_present": (d / "Wetlandmap.shp").exists(),
            "gcp_shapefile_attributes_present": (d / "GroundControlPoint.dbf").exists(),
            "wetlandmap_tfw_pixel_deg": tfw[0], "wetlandmap_tfw_pixel_m_approx": round(tfw[0] * 111_320, 1),
            "gcp_rows": int(len(gcp)), "gcp_classes": gcp["Landcover_type"].value_counts().to_dict(),
            "gcp_points": stats, "gcp_coordinate_decimals": _decimals(gcp["Location_x"]),
            "gcp_low_precision_lt3_decimals": int((dec < 3).sum()),
            "gcp_duplicate_coordinates": int(gcp.duplicated(["Location_x", "Location_y"]).sum()),
            "gcp_observation_date": "not recorded in file",
            "eligibility": {
                "wetland_map_display": "NO — map raster/vector geometry absent from the archive",
                "wetland_classifier_labels": "CANDIDATE — ~1k labelled points, 8 classes; no dates; need "
                                             "date-matched imagery (DE Africa S2/S1) and spatial-block splits; "
                                             "drop invalid/low-precision points"}}


def audit_eo4forest(b: Boundary) -> dict:
    base = RAW_DIR / "eo4forest_lagos_ogun" / "extracted"
    tv = base / "TrainingAndValidationSamples"
    if not tv.exists():
        return _missing("eo4forest_lagos_ogun", [str(tv)])
    tr = pyogrio.read_dataframe(tv / "training_samples" / "training_samples.shp", columns=["class", "layer"])
    va = pyogrio.read_dataframe(tv / "validation_samples" / "validation_samples.shp", columns=["class", "layer"])
    # Leakage check: how close is each validation point to the nearest training point?
    xy_tr = np.c_[tr.geometry.x, tr.geometry.y]
    xy_va = np.c_[va.geometry.x, va.geometry.y]
    dist, _ = KDTree(xy_tr).query(xy_va, k=1)
    dist = dist.ravel()
    exact_dups = int(pd.MultiIndex.from_arrays([xy_va[:, 0].round(2), xy_va[:, 1].round(2)])
                     .isin(pd.MultiIndex.from_arrays([xy_tr[:, 0].round(2), xy_tr[:, 1].round(2)])).sum())
    va_ll = va.to_crs(4326)
    stats = _point_stats(va_ll.geometry.x, va_ll.geometry.y, b)
    maps = {}
    cm = base / "ClassificationMaps"
    for tif in sorted(cm.glob("*.tif")) if cm.exists() else []:
        with rasterio.open(tif) as r:
            maps[tif.name] = {"crs": str(r.crs), "res": r.res, "shape": r.shape, "dtype": r.dtypes[0], "nodata": r.nodata}
    acc = {}
    for txt in sorted(cm.glob("Accuracy_*.txt")) if cm.exists() else []:
        m = re.search(r"Overall Accuracy for all classes:\s*([\d.]+)", txt.read_text())
        f3 = re.search(r"Class 3:\s*([\d.]+)", txt.read_text())
        acc[txt.name] = {"overall_accuracy": float(m.group(1)) if m else None, "f1_class3_soil": float(f3.group(1)) if f3 else None}
    legend = (cm / "color_map_classification.clr").read_text().splitlines() if (cm / "color_map_classification.clr").exists() else []
    return {"status": "ok", "crs_samples": str(tr.crs), "training_points": int(len(tr)), "validation_points": int(len(va)),
            "stated_in_record": {"training": 112000, "validation": 11900},
            "training_class_counts": tr["layer"].value_counts().to_dict(),
            "validation_class_counts": va["layer"].value_counts().to_dict(),
            "validation_points_geo": stats,
            "val_to_nearest_train_m": {"p05": round(float(np.percentile(dist, 5)), 1), "median": round(float(np.median(dist)), 1),
                                       "p95": round(float(np.percentile(dist, 95)), 1), "share_lt_100m": round(float((dist < 100).mean()), 3),
                                       "exact_coordinate_overlap": exact_dups},
            "legend": legend, "published_accuracy": acc, "maps_extracted": maps,
            "eligibility": {
                "land_cover_display": "YES — published map, 20 m, label as 'EO4Forest RF classification (year)'",
                "visible_surface_labels": "CANDIDATE — photo-interpreted classes; 'Soil' = bare ground, NOT sand",
                "independent_accuracy": "NO — published validation points sit close to training points "
                                        "(see val_to_nearest_train_m); scores are optimistic, not independent"}}


def audit_hadejia(b: Boundary) -> dict:
    base = RAW_DIR / "hadejia_flood" / "extracted"
    if not base.exists():
        return _missing("hadejia_flood", [str(base)])
    out: dict = {"status": "ok"}
    sa = gpd.read_file(base / "Study_Area_Shp" / "Hadejia_boundary_FAO_UTM_32N.shp")
    out["study_area"] = {"crs": str(sa.crs), "area_km2": round(float(sa.area.sum() / 1e6), 2),
                         "adm2": sa["ADM2_NAME"].tolist(), "adm1": sa["ADM1_NAME"].tolist()}
    c = sa.geometry.centroid.to_crs(4326).iloc[0]
    out["study_area"]["centroid_inside_nigeria"] = bool(b.contains([c.x], [c.y])[0])
    rasters = {}
    for tif in sorted(base.glob("Flood_Extent_Layers_RF_S1_and_PS/*/Combined_*.tif")) + \
               sorted(base.glob("Flood_Frequency_Layers/*.tif")) + sorted(base.glob("Perm_Water_Layer/*.tif")) + \
               sorted(base.glob("Land_Cover_Layers/*.tif")):
        with rasterio.open(tif) as r:
            rasters[str(tif.relative_to(base))] = {"crs": str(r.crs), "res_m": r.res, "shape": r.shape,
                                                   "dtype": r.dtypes[0], "nodata": r.nodata}
    out["rasters"] = rasters
    per_date = sorted(p.name for p in base.glob("Flood_Extent_Layers_RF_S1_and_PS/*/*_flood_layer.tif"))
    out["per_date_flood_layers"] = per_date
    tp = {}
    for shp in sorted(base.glob("Flood_Accuracy_Assessment/Flood_Testing_Points/*.shp")):
        g = gpd.read_file(shp)
        tp[shp.name] = {"n": int(len(g)), "label_field": "MNDWI_Valu", "counts": g["MNDWI_Valu"].value_counts().to_dict()}
    out["testing_points"] = tp
    s = pd.read_csv(base / "Survey_Data" / "Form_Responses_Cleaned.csv")
    out["survey_rows_released"] = int(len(s))
    note = base / "Survey_Data" / "Note_on_Survey_Data.txt"
    out["survey_note"] = note.read_text().strip() if note.exists() else None
    out["eligibility"] = {
        "flood_extent_history_display": "YES — 2020/2022 event extents, dated per scene, 3 m, Hadejia LGA only (~48 km2)",
        "independent_flood_evaluation": "PARTIAL — 300 test points/year labelled from Sentinel-2 MNDWI maps (a "
                                        "different sensor than the S1/PlanetScope extents) — sensor-independent but "
                                        "still EO-derived, not field truth",
        "participatory_truth": "NO — only 5 survey responses released"}
    return out


def audit_geotech() -> dict:
    p = RAW_DIR / "geotech_ibadan" / "geotech_ibadan.xlsx"
    if not p.exists():
        return _missing("geotech_ibadan", [str(p)])
    x = pd.read_excel(p, sheet_name=None)
    sheet, df = next(iter(x.items()))
    samples = df.iloc[:, 0].dropna().astype(str)
    pits = sorted({re.match(r"P\d+", s).group(0) for s in samples if re.match(r"P\d+", s)})
    has_coords = any(re.search(r"lat|lon|easting|northing|coord", str(c), re.I) for c in df.columns)
    return {"status": "ok", "sheets": list(x), "rows": int(len(samples)), "pits": pits, "columns": [str(c) for c in df.columns],
            "coordinates_present": has_coords, "cbr_present": any("CBR" in str(c).upper() for c in df.columns),
            "eligibility": {"model_training": "NO — 9 pits, no coordinates, no outcomes",
                            "context_display": "LIMITED — Ibadan-area engineering ranges only, cannot be mapped to a point"}}


def audit_hydrobasins(b: Boundary) -> dict:
    out = {}
    for lev in ("06", "08"):
        p = RAW_DIR / "hydrobasins_af" / "extracted" / f"hybas_af_lev{lev}_v1c.shp"
        if not p.exists():
            out[f"lev{lev}"] = _missing("hydrobasins_af", [str(p)])
            continue
        g = gpd.read_file(p)
        hits = g[g.intersects(b.geometry)]
        out[f"lev{lev}"] = {"status": "ok", "crs": str(g.crs), "africa_basins": int(len(g)),
                            "basins_intersecting_nigeria": int(len(hits)), "fields": [c for c in g.columns if c != "geometry"],
                            "hybas_id_unique": bool(g["HYBAS_ID"].is_unique),
                            "next_down_resolves": bool(g.loc[g.NEXT_DOWN != 0, "NEXT_DOWN"].isin(g.HYBAS_ID).all())}
    out["eligibility"] = {"basin_identity": "YES — verified IDs + topology (NEXT_DOWN); drainage units, NOT wetlands"}
    return out


def audit_wofs(b: Boundary) -> dict:
    from terrasense.ingest.wofs import OUT, nigeria_tiles
    tiles = nigeria_tiles()
    have = [t for t in tiles if (OUT / f"x{t[0]:03d}y{t[1]:03d}").exists()]
    if not have:
        return _missing("deafrica_wofs", [str(OUT)])
    stac = json.loads(next((OUT / f"x{have[0][0]:03d}y{have[0][1]:03d}").glob("*.stac-item.json")).read_text())["properties"]
    f = next((OUT / f"x{have[0][0]:03d}y{have[0][1]:03d}").glob("*_count_clear.tif"))
    with rasterio.open(f) as r:
        meta = {"crs": str(r.crs), "res": r.res, "dtype": r.dtypes[0], "nodata": r.nodata, "shape": r.shape}
    rules = __import__("terrasense.config", fromlist=["x"]).load_assessment_rules()["wofs"]
    return {"status": "ok", "tiles_intersecting_nigeria": len(tiles), "tiles_present": len(have),
            "period": [stac["dtr:start_datetime"], stac["dtr:end_datetime"]], "product_version": stac["odc:dataset_version"],
            "processed": stac["odc:processing_datetime"], "raster": meta,
            "hazard_rule_min_wet_observations": rules["min_wet_observations"],
            "eligibility": {"historical_water_frequency": "YES — national 30 m coverage, dated 1984-2025, quality via count_clear",
                            "live_flood": "NO — historical summary only"}}


def audit_soilgrids(b: Boundary) -> dict:
    from terrasense.ingest.soilgrids import DEPTHS, OUT, PROPS, STATS
    expected = [f"{p}_{d}_{s}.tif" for p in PROPS for d in DEPTHS for s in STATS]
    present = [n for n in expected if (OUT / n).exists()]
    if not present:
        return _missing("soilgrids", [str(OUT)])
    with rasterio.open(OUT / present[0]) as r:
        meta = {"crs_name": r.crs.to_wkt().split('"')[1], "res_m": r.res, "dtype": r.dtypes[0], "nodata": r.nodata,
                "shape": r.shape, "tags": {k: v for k, v in r.tags().items() if k in ("Model", "Code_version", "WoSIS_version", "mapped_unit")}}
    # compositional check on a sample of in-Nigeria pixels for complete depth/mean triplets
    checks = {}
    rng = np.random.default_rng(0)
    minx, miny, maxx, maxy = b.geometry.bounds
    lon = rng.uniform(minx, maxx, 4000)
    lat = rng.uniform(miny, maxy, 4000)
    keep = b.contains(lon, lat)
    lon, lat = lon[keep][:1000], lat[keep][:1000]
    from pyproj import Transformer
    for d in DEPTHS:
        names = [f"{p}_{d}_mean.tif" for p in PROPS]
        if not all((OUT / n).exists() for n in names):
            continue
        sums = None
        for n in names:
            with rasterio.open(OUT / n) as r:
                x, y = Transformer.from_crs(4326, r.crs, always_xy=True).transform(lon, lat)
                v = np.array([s[0] for s in r.sample(zip(x, y))], dtype=float)
                v[v == r.nodata] = np.nan
                sums = v if sums is None else sums + v
        sums = sums / 10
        ok = ~np.isnan(sums)
        checks[d] = {"n": int(ok.sum()), "sum_of_means_pct_p01_p50_p99": [round(float(q), 1) for q in np.percentile(sums[ok], [1, 50, 99])],
                     "nodata_share": round(float(1 - ok.mean()), 3)}
    mask_tags = {}
    for n in present:
        with rasterio.open(OUT / n) as r:
            t = r.tags()
        mask_tags[n] = {"retrieval": "wcs" if "WCS" in t.get("retrieval", "") else "vrt",
                        "zeros_kept_as_data": int(t.get("zeros_outside_reference_mask", 0)),
                        "nonzero_inside_mask_REVIEW": int(t.get("nonzero_inside_reference_mask", 0))}
    review = [n for n, v in mask_tags.items() if v["nonzero_inside_mask_REVIEW"]]
    return {"status": "ok" if len(present) == len(expected) else "partial", "layers_expected": len(expected),
            "layers_with_genuine_zeros": {n: v["zeros_kept_as_data"] for n, v in mask_tags.items() if v["zeros_kept_as_data"]},
            "layers_needing_mask_review": review,
            "retrieval_counts": {k: sum(v["retrieval"] == k for v in mask_tags.values()) for k in ("wcs", "vrt")},
            "layers_present": len(present), "raster": meta, "composition_check_by_depth": checks,
            "eligibility": {"modelled_prior_display": "YES — labelled MODELLED with Q05-Q95 interval, native 250 m",
                            "validation_truth": "NO — model output; never evaluate against it"}}


AUDITORS = {
    "geoboundaries_nga": lambda b: audit_boundary(),
    "s4a_field": audit_s4a_field,
    "ozoro_texture": lambda b: audit_ozoro(),
    "wetland_south_ng": audit_wetland,
    "eo4forest_lagos_ogun": audit_eo4forest,
    "hadejia_flood": audit_hadejia,
    "geotech_ibadan": lambda b: audit_geotech(),
    "hydrobasins_af": audit_hydrobasins,
    "deafrica_wofs": audit_wofs,
    "soilgrids": audit_soilgrids,
}


def run_audit() -> dict:
    b = nigeria()
    reg = load_registry()
    results = {}
    for sid, fn in AUDITORS.items():
        try:
            results[sid] = fn(b)
        except Exception as exc:  # report, never hide
            results[sid] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
    not_audited = [s["id"] for s in reg["sources"] if s["id"] not in AUDITORS]
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "boundary": b.source, "results": results,
            "not_audited": {sid: next(s for s in reg["sources"] if s["id"] == sid).get("status", "not_audited")
                            for sid in not_audited}}


def write_audit(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str))
    return path
