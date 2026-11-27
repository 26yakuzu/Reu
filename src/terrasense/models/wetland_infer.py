"""Optional inference with the wetland RF — active ONLY if its pre-registered deployment gate passed.

Needs network access to DE Africa GeoMAD 2018 COGs at query time; offline it returns
`unavailable`. Points outside the training domain (convex hull of training labels + 10 km)
return `outside_coverage`. Output is a modelled 2018 class, never current conditions.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import wkt
from shapely.geometry import Point

from terrasense.geo.layers import Reading
from terrasense.ingest.wofs import tile_of
from terrasense.models import wetland as W

RESULTS = W.REPORT_DIR / "wetland_rf_results.json"
MODEL = W.MODEL_DIR / "wetland_rf_geomad2018.joblib"


@lru_cache(maxsize=1)
def _bundle():
    if not (RESULTS.exists() and MODEL.exists()):
        return None
    res = json.loads(RESULTS.read_text())
    if not res.get("deployment_gate", {}).get("passed"):
        return None
    import joblib
    b = joblib.load(MODEL)
    b["domain"] = wkt.loads(b["domain_wkt_6933"])
    b["test_macro_f1"] = res["random_forest_test"]["macro_f1"]
    b["ci"] = res.get("block_bootstrap_95ci", {}).get("rf_macro_f1")
    b["per_class_f1"] = {k: v["f1-score"] for k, v in res["random_forest_test"]["per_class"].items()}
    return b


def enabled() -> bool:
    return _bundle() is not None


def wetland_model_reading(lon: float, lat: float) -> Reading | None:
    b = _bundle()
    if b is None:
        return None
    base = dict(layer_id="wetland_rf_geomad2018", title="Modelled wetland class, 2018 (Random Forest, research)",
                theme="wetland_model", observation="2018 (Sentinel-2 annual geomedian)", native_resolution_m=10.0,
                crs="EPSG:6933", source_id="wetland_south_ng", doi="10.5518/1314", licence="CC-BY-4.0",
                caveats=[f"Model output, held-out macro-F1 {b['test_macro_f1']:.2f} (95% block-bootstrap CI {b['ci']}) on "
                         "spatial blocks from the same labelling campaign (not externally independent).",
                         "Per-class held-out F1: " + ", ".join(f"{k} {v:.2f}" for k, v in b["per_class_f1"].items())
                         + " — vegetated wetland is frequently confused with 'other'.",
                         "Display only: a modelled class never triggers the observed-hazard state.",
                         "Class probabilities are uncalibrated and are not shown.",
                         "2018 conditions; wetlands change seasonally and between years."])
    x, y = Transformer.from_crs(4326, 6933, always_xy=True).transform(lon, lat)
    if not b["domain"].contains(Point(x, y)):
        return Reading(status="outside_coverage", **base)
    pts = pd.DataFrame({"x6933": [x], "y6933": [y], "lon": [lon], "lat": [lat]})
    try:
        feats = W._sample_tile(tile_of(x, y), pts)
    except Exception:
        return Reading(status="unavailable", **base)
    df = W.add_indices(pd.concat([pts, feats, W._wofs_features(pts)], axis=1))
    X = df[b["features"]]
    if X.isna().any(axis=None):
        return Reading(status="nodata", **base)
    cls = str(b["model"].predict(X.values)[0])
    return Reading(status="value", label=cls.replace("_", " "), value=None, **base)
