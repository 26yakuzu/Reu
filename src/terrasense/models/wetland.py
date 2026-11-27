"""Wetland / open-water classifier (southern Nigeria) — data, features, splits, training, evaluation.

Labels  : Garba et al. (2023) ground control points (doi:10.5518/1314), after QC (1,016 points).
          Undated in the source; the study's map year is 2018.
Features: DE Africa Sentinel-2 annual GeoMAD 2018 (10 m, CC BY 4.0) + MAD bands + indices,
          DE Africa WOfS all-time frequency (30 m). 3x3-pixel median at each point to absorb the
          ~11 m precision of 4-decimal coordinates.
Target  : 3 classes — open_water / vegetated_wetland / other.

Honesty constraints enforced in code:
* test set = whole spatial blocks, chosen once (seeded), never used for model selection;
* training points within BUFFER_M of any test point are dropped (leakage buffer);
* baselines are evaluated on the same test set;
* the test set comes from the same labelling campaign, so scores are spatially held-out
  but NOT externally independent — reported as such.
"""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from terrasense.config import ARTIFACTS_DIR, PROCESSED_DIR
from terrasense.geo.layers import current_dir
from terrasense.ingest.wofs import tile_of
from terrasense.models.splits import block_ids, leakage_report

SEED = 20261127
GEOMAD_YEAR = 2018
GEOMAD_URL = ("https://deafrica-services.s3.af-south-1.amazonaws.com/gm_s2_annual/1-0-0/"
              "x{ix:03d}/y{iy:03d}/{y}--P1Y/gm_s2_annual_x{ix:03d}y{iy:03d}_{y}--P1Y_{band}.tif")
BANDS = ("B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12", "EMAD", "SMAD", "BCMAD", "COUNT")
LABEL_MAP = {"Deep water": "open_water", "Shallow water": "open_water",
             "Mangrove": "vegetated_wetland", "Swamp": "vegetated_wetland", "Marsh": "vegetated_wetland",
             "Forest": "other", "Cultivated land": "other", "Built up/bare land": "other"}
CLASSES = ("open_water", "vegetated_wetland", "other")
BLOCK_M = 25_000          # spatial block edge (EPSG:6933 metres)
BUFFER_M = 2_000          # drop training points this close to any test point
TEST_FRACTION = 0.2
FEATURES_PATH = PROCESSED_DIR / "features" / f"wetland_gcp_features_geomad{GEOMAD_YEAR}.parquet"
REPORT_DIR = ARTIFACTS_DIR / "reports"
MODEL_DIR = ARTIFACTS_DIR / "models"


# ---------------------------------------------------------------- features

def load_labels() -> gpd.GeoDataFrame:
    g = gpd.read_parquet(current_dir() / "wetland_gcp_south_ng.parquet")
    g = g[g.qc_reject_reason == ""].copy()
    g["target"] = g.class_name.map(LABEL_MAP)
    if g.target.isna().any():
        raise ValueError(f"unmapped classes: {g.loc[g.target.isna(), 'class_name'].unique()}")
    x, y = Transformer.from_crs(4326, 6933, always_xy=True).transform(g.lon.values, g.lat.values)
    g["x6933"], g["y6933"] = x, y
    return g.reset_index(drop=True)


def _sample_tile(tile, pts: pd.DataFrame) -> pd.DataFrame:
    ix, iy = tile
    rows = {i: {} for i in pts.index}
    # HTTP timeout is essential: without it a stalled range request blocks forever (observed 2026-11-27)
    env = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT=60, GDAL_HTTP_CONNECTTIMEOUT=20,
               GDAL_HTTP_MAX_RETRY=4, GDAL_HTTP_RETRY_DELAY=3, CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
               VSI_CACHE=True, GDAL_CACHEMAX=256)
    with rasterio.Env(**env):
        for band in BANDS:
            url = "/vsicurl/" + GEOMAD_URL.format(ix=ix, iy=iy, y=GEOMAD_YEAR, band=band)
            try:
                with rasterio.open(url) as ds:
                    nd = ds.nodata
                    for i, p in pts.iterrows():
                        r, c = ds.index(p.x6933, p.y6933)
                        win = ((max(r - 1, 0), r + 2), (max(c - 1, 0), c + 2))
                        a = ds.read(1, window=win).astype(float)
                        if nd is not None:
                            a[a == nd] = np.nan
                        rows[i][band] = float(np.nanmedian(a)) if np.isfinite(a).any() else np.nan
            except rasterio.errors.RasterioIOError:
                for i in pts.index:
                    rows[i][band] = np.nan
    return pd.DataFrame.from_dict(rows, orient="index")


def _wofs_features(g: pd.DataFrame) -> pd.DataFrame:
    from terrasense.geo.layers import wofs_reading
    out = []
    for lon, lat in zip(g.lon, g.lat):
        r = wofs_reading(lon, lat)
        out.append({"wofs_freq": r.value if r.status == "value" else np.nan,
                    "wofs_clear": (r.counts or {}).get("clear", np.nan)})
    return pd.DataFrame(out, index=g.index)


def build_features(workers: int = 6, force: bool = False) -> Path:
    """Sample GeoMAD 2018 at every label point. Per-tile results are checkpointed under
    features/_tiles/ so an interrupted run resumes; a tile with failed reads is retried."""
    if FEATURES_PATH.exists() and not force:
        return FEATURES_PATH
    g = load_labels()
    g["tile"] = [tile_of(x, y) for x, y in zip(g.x6933, g.y6933)]
    groups = list(g.groupby("tile"))
    ckpt = FEATURES_PATH.parent / "_tiles"
    ckpt.mkdir(parents=True, exist_ok=True)
    done = {"n": 0}

    def run(kv):
        (ix, iy), pts = kv
        f = ckpt / f"x{ix:03d}y{iy:03d}_{GEOMAD_YEAR}.parquet"
        if f.exists() and not force:
            part = pd.read_parquet(f)
        else:
            for attempt in range(3):
                part = _sample_tile((ix, iy), pts)
                if part[list(BANDS)].notna().any(axis=1).all():   # every point got at least one band
                    break
            part.to_parquet(f)
        done["n"] += 1
        print(f"[features] tile x{ix:03d}y{iy:03d}: {len(pts)} pts, "
              f"{int(part[list(BANDS)].isna().any(axis=1).sum())} incomplete — {done['n']}/{len(groups)} tiles", flush=True)
        return part

    with ThreadPoolExecutor(workers) as ex:
        parts = list(ex.map(run, groups))
    feats = pd.concat(parts).sort_index()
    df = pd.concat([g.drop(columns=["geometry", "tile"]), feats, _wofs_features(g)], axis=1)
    df = add_indices(df)
    df.attrs = {}
    df.to_parquet(FEATURES_PATH)
    meta = {"generated_at": _now(), "geomad_year": GEOMAD_YEAR, "bands": BANDS, "n_points": int(len(df)),
            "n_tiles": len(groups), "window": "3x3 median at 10 m", "label_source": "wetland_south_ng (doi:10.5518/1314)",
            "imagery_source": "DE Africa gm_s2_annual 1-0-0 (CC BY 4.0)",
            "rows_with_any_missing_feature": int(df[FEATURE_COLS].isna().any(axis=1).sum()),
            "sha256": _sha256(FEATURES_PATH)}
    FEATURES_PATH.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return FEATURES_PATH


def add_indices(df: pd.DataFrame) -> pd.DataFrame:
    s = lambda a, b: (df[a] - df[b]) / (df[a] + df[b])
    df["NDVI"] = s("B08", "B04")
    df["MNDWI"] = s("B03", "B11")
    df["NDWI"] = s("B03", "B08")
    df["NDMI"] = s("B8A", "B11")
    return df


FEATURE_COLS = [*[b for b in BANDS if b != "COUNT"], "NDVI", "MNDWI", "NDWI", "NDMI", "wofs_freq"]


# ---------------------------------------------------------------- split

def make_split(df: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """'train' / 'test' / 'buffer_dropped' per row. Test = whole blocks; stratification is not
    attempted (it would require peeking at labels per block beyond counts)."""
    blocks = block_ids(df.x6933.values, df.y6933.values, BLOCK_M)
    uniq = np.unique(blocks)
    rng = np.random.default_rng(SEED)
    rng.shuffle(uniq)
    test_blocks, n = set(), 0
    for b in uniq:                                  # add whole blocks until ~TEST_FRACTION of points
        if n >= TEST_FRACTION * len(df):
            break
        test_blocks.add(b)
        n += int((blocks == b).sum())
    split = np.where(np.isin(blocks, list(test_blocks)), "test", "train").astype(object)
    xy = np.c_[df.x6933.values, df.y6933.values]
    from sklearn.neighbors import KDTree
    d, _ = KDTree(xy[split == "test"]).query(xy[split == "train"], k=1)
    tr_idx = np.where(split == "train")[0]
    split[tr_idx[d.ravel() < BUFFER_M]] = "buffer_dropped"
    rep = leakage_report(xy[split == "train"], xy[split == "test"], min_gap_m=BUFFER_M)
    rep.update({"block_m": BLOCK_M, "buffer_m": BUFFER_M, "n_blocks_total": int(len(uniq)),
                "n_test_blocks": len(test_blocks), "n_buffer_dropped": int((split == "buffer_dropped").sum())})
    return split, rep


# ---------------------------------------------------------------- training / evaluation

def _metrics(y_true, y_pred) -> dict:
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, jaccard_score
    labels = list(CLASSES)
    return {"n": int(len(y_true)), "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "macro_f1": round(float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 4),
            "per_class": {k: {m: round(float(v), 4) for m, v in d.items()} for k, d in
                          classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0).items()
                          if k in labels},
            "iou": dict(zip(labels, [round(float(v), 4) for v in
                                     jaccard_score(y_true, y_pred, labels=labels, average=None, zero_division=0)])),
            "confusion_matrix": {"labels": labels, "rows_true_cols_pred":
                                 confusion_matrix(y_true, y_pred, labels=labels).tolist()}}


def rule_baseline(df: pd.DataFrame) -> np.ndarray:
    """Transparent non-learned rule: open water if WOfS freq >= 0.5 or MNDWI > 0; else 'other'.
    (No rule for vegetated wetland exists in the source layers — that is the point of the test.)"""
    w = (df.wofs_freq.fillna(0) >= 0.5) | (df.MNDWI.fillna(-1) > 0)
    return np.where(w, "open_water", "other")


def train_and_evaluate(features_path: Path = FEATURES_PATH) -> dict:
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import GroupKFold, GridSearchCV
    from sklearn.dummy import DummyClassifier

    df = pd.read_parquet(features_path)
    complete = df[FEATURE_COLS].notna().all(axis=1)
    dropped_incomplete = int((~complete).sum())
    df = df[complete].reset_index(drop=True)
    split, leak = make_split(df)
    tr, te = df[split == "train"], df[split == "test"]
    # pandas>=3 returns ArrowStringArray from .values on string columns; sklearn needs plain numpy
    Xtr, Xte = tr[FEATURE_COLS].to_numpy(dtype=float), te[FEATURE_COLS].to_numpy(dtype=float)
    ytr, yte = tr.target.to_numpy(dtype=object), te.target.to_numpy(dtype=object)

    results = {"generated_at": _now(), "seed": SEED, "features": FEATURE_COLS, "classes": CLASSES,
               "label_map": LABEL_MAP, "n_total_complete": int(len(df)), "dropped_incomplete_features": dropped_incomplete,
               "split": leak,
               "class_counts": {"train": tr.target.value_counts().to_dict(), "test": te.target.value_counts().to_dict()}}

    maj = DummyClassifier(strategy="most_frequent").fit(Xtr, ytr)
    results["baseline_majority"] = _metrics(yte, maj.predict(Xte))
    results["baseline_rule_wofs_mndwi"] = _metrics(yte, rule_baseline(te))

    groups = block_ids(tr.x6933.values, tr.y6933.values, BLOCK_M)
    n_splits = min(5, len(np.unique(groups)))
    grid = {"max_depth": [None, 12], "min_samples_leaf": [1, 3, 8], "max_features": ["sqrt", 0.5]}
    rf = RandomForestClassifier(n_estimators=400, class_weight="balanced", random_state=SEED, n_jobs=-1)
    gs = GridSearchCV(rf, grid, cv=GroupKFold(n_splits=n_splits), scoring="f1_macro", n_jobs=1, refit=True)
    gs.fit(Xtr, ytr, groups=groups)
    results["rf_search"] = {"grid": grid, "cv": f"GroupKFold({n_splits}) over {BLOCK_M // 1000} km blocks",
                            "best_params": gs.best_params_, "best_cv_macro_f1": round(float(gs.best_score_), 4),
                            "cv_macro_f1_std": round(float(gs.cv_results_["std_test_score"][gs.best_index_]), 4)}
    pred = gs.best_estimator_.predict(Xte)
    results["random_forest_test"] = _metrics(yte, pred)
    # block bootstrap (resample whole test blocks) for 95% CIs — points within a block are not independent
    from sklearn.metrics import f1_score
    te_blocks = block_ids(te.x6933.values, te.y6933.values, BLOCK_M)
    ub = np.unique(te_blocks)
    base_pred = rule_baseline(te)
    rng = np.random.default_rng(SEED)
    rf_s, base_s, diff_s, wet_s = [], [], [], []
    for _ in range(2000):
        pick = rng.choice(ub, size=len(ub), replace=True)
        idx = np.concatenate([np.where(te_blocks == b)[0] for b in pick])
        f_rf = f1_score(yte[idx], pred[idx], labels=list(CLASSES), average="macro", zero_division=0)
        f_b = f1_score(yte[idx], base_pred[idx], labels=list(CLASSES), average="macro", zero_division=0)
        rf_s.append(f_rf); base_s.append(f_b); diff_s.append(f_rf - f_b)
        wet_s.append(f1_score(yte[idx], pred[idx], labels=["vegetated_wetland"], average="macro", zero_division=0))
    ci = lambda a: [round(float(np.percentile(a, 2.5)), 3), round(float(np.percentile(a, 97.5)), 3)]
    results["block_bootstrap_95ci"] = {"n_boot": 2000, "unit": f"test block ({BLOCK_M // 1000} km)", "n_blocks": int(len(ub)),
                                       "rf_macro_f1": ci(rf_s), "rule_baseline_macro_f1": ci(base_s),
                                       "rf_minus_rule_macro_f1": ci(diff_s), "rf_vegetated_wetland_f1": ci(wet_s)}
    imp = sorted(zip(FEATURE_COLS, gs.best_estimator_.feature_importances_), key=lambda t: -t[1])
    results["rf_feature_importance"] = {k: round(float(v), 4) for k, v in imp}

    # performance by region (ADM1 of test points)
    from terrasense.geo.boundary import nigeria
    b = nigeria()
    te_state = [b.state_of(lo, la) for lo, la in zip(te.lon, te.lat)]
    by = {}
    for s in sorted(set(te_state)):
        m = np.array(te_state) == s
        by[s] = {"n": int(m.sum()), "accuracy": round(float((pred[m] == yte[m]).mean()), 3)}
    results["random_forest_test_by_state"] = by

    # domain: convex hull of training points (buffered 10 km) — predictions outside are refused
    tr_pts = gpd.GeoSeries(gpd.points_from_xy(tr.x6933, tr.y6933), crs=6933)
    domain = tr_pts.union_all().convex_hull.buffer(10_000)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    mpath = MODEL_DIR / "wetland_rf_geomad2018.joblib"
    joblib.dump({"model": gs.best_estimator_, "features": FEATURE_COLS, "classes": CLASSES,
                 "domain_wkt_6933": domain.wkt, "geomad_year": GEOMAD_YEAR}, mpath)
    results["artifact"] = {"path": str(mpath.relative_to(ARTIFACTS_DIR.parent)), "sha256": _sha256(mpath)}
    results["features_sha256"] = _sha256(features_path)

    # deployment gate: must beat BOTH baselines on held-out macro-F1 by a clear margin
    best_base = max(results["baseline_majority"]["macro_f1"], results["baseline_rule_wofs_mndwi"]["macro_f1"])
    rf_f1 = results["random_forest_test"]["macro_f1"]
    results["deployment_gate"] = {"rule": "RF held-out macro-F1 >= best baseline + 0.10 and >= 0.60 "
                                          "(pre-registered before results were seen)",
                                  "best_baseline_macro_f1": best_base, "rf_macro_f1": rf_f1,
                                  "passed": bool(rf_f1 >= best_base + 0.10 and rf_f1 >= 0.60),
                                  "note": "Bootstrap CIs are reported alongside; the gate itself uses the point estimate."}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "wetland_rf_results.json").write_text(json.dumps(results, indent=2, default=str))
    return results


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
