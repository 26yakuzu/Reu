"""Point lookups against verified, processed layers.

A reading is always one of:
  value            — the layer covers the point and has data there
  nodata           — covered, but the pixel is nodata/masked
  outside_coverage — the layer does not cover this location
  unavailable      — the processed file is missing (not fetched / not prepared)
No reading is ever interpolated, resampled or filled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import Point

from terrasense.config import PROCESSED_DIR, source_by_id
from terrasense.geo.crs import utm_for


def current_dir() -> Path:
    cur = PROCESSED_DIR / "CURRENT"
    return PROCESSED_DIR / cur.read_text().strip() if cur.exists() else PROCESSED_DIR / "_missing_"


@dataclass(frozen=True)
class RasterLayer:
    id: str
    source_id: str
    title: str
    theme: str
    observation: str                 # human-readable observation period
    legend: dict[int, str] | None
    value_kind: str                  # class | binary | count_of_n | presence
    n_scenes: int | None = None
    caveats: tuple[str, ...] = ()

    @property
    def path(self) -> Path:
        return current_dir() / f"{self.id}.tif"


EO4F_LEGEND = {1: "Water", 2: "Urbanized", 3: "Soil (bare ground — not a texture class)", 4: "Cropland", 5: "Grassland", 6: "Forest"}
HAD_LC_LEGEND = {1: "Bare soil (surface cover — not a texture class)", 2: "Built-up", 3: "Cultivated land", 4: "Fallow land", 5: "Tree", 6: "Water"}

RASTER_LAYERS: tuple[RasterLayer, ...] = (
    RasterLayer("eo4forest_landcover_2023-12", "eo4forest_lagos_ogun", "EO4Forest land cover, Dec 2023 (Lagos/Ogun)",
                "visible_surface", "2023-12 (Sentinel-2/Landsat-8 composite)", EO4F_LEGEND, "class",
                caveats=("Random Forest map product, not field observation.",
                         "Publisher-reported F1 for 'Soil' class 0.73 (2023-12), computed on validation points located near training points — optimistic.")),
    RasterLayer("hadejia_landcover_2022", "hadejia_flood", "Hadejia land cover 2022", "visible_surface", "2022",
                HAD_LC_LEGEND, "class", caveats=("Classifier product for Hadejia LGA only.",)),
    RasterLayer("hadejia_flood_extent_2020", "hadejia_flood", "Hadejia combined flood extent, 2020 event", "flood_history",
                "2020-08-14 to 2020-10-28 (11 Sentinel-1/PlanetScope scenes)", {0: "Not mapped as flooded", 1: "Flooded at least once"},
                "binary", caveats=("Historical event map — NOT current conditions.", "Says nothing about depth or flow.",
                                   "Publisher nodata (0) coincides with 'not flooded'; absence of flooding cannot be distinguished from no data.")),
    RasterLayer("hadejia_flood_extent_2022", "hadejia_flood", "Hadejia combined flood extent, 2022 event", "flood_history",
                "2022-08-04 to 2022-10-28 (12 Sentinel-1/PlanetScope scenes)", {0: "Not mapped as flooded", 1: "Flooded at least once"},
                "binary", caveats=("Historical event map — NOT current conditions.", "Says nothing about depth or flow.",
                                   "Publisher nodata (0) coincides with 'not flooded'; absence of flooding cannot be distinguished from no data.")),
    RasterLayer("hadejia_flood_freq_2020", "hadejia_flood", "Hadejia flood frequency 2020 (cropland only)", "flood_history",
                "2020 event, 11 scenes", None, "count_of_n", n_scenes=11, caveats=("Masked to cropland; non-cropland is nodata.",)),
    RasterLayer("hadejia_flood_freq_2022", "hadejia_flood", "Hadejia flood frequency 2022 (cropland only)", "flood_history",
                "2022 event, 12 scenes", None, "count_of_n", n_scenes=12, caveats=("Masked to cropland; non-cropland is nodata.",)),
    RasterLayer("hadejia_perm_water_2022", "hadejia_flood", "Hadejia permanent water 2022", "water", "2022", {1: "Permanent water"},
                "presence", caveats=("Pixels outside the permanent-water mask are nodata in the source.",)),
)


@dataclass
class Reading:
    layer_id: str
    title: str
    theme: str
    status: str
    value: float | int | None = None
    label: str | None = None
    source_id: str | None = None
    doi: str | None = None
    licence: str | None = None
    observation: str | None = None
    native_resolution_m: float | None = None
    crs: str | None = None
    measured: bool = False
    historical: bool = True
    distance_m: float | None = None
    counts: dict | None = None
    caveats: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _prov(source_id: str) -> dict:
    s = source_by_id(source_id)
    return {"source_id": source_id, "doi": s.get("doi"), "licence": s.get("licence")}


@lru_cache(maxsize=32)
def _open(path: str):
    return rasterio.open(path)


@lru_cache(maxsize=8)
def _tx(epsg: str):
    return Transformer.from_crs("EPSG:4326", epsg, always_xy=True)


def sample_raster(layer: RasterLayer, lon: float, lat: float) -> Reading:
    base = dict(layer_id=layer.id, title=layer.title, theme=layer.theme, observation=layer.observation,
                caveats=list(layer.caveats), **_prov(layer.source_id))
    if not layer.path.exists():
        return Reading(status="unavailable", **base)
    ds = _open(str(layer.path))
    x, y = _tx(ds.crs.to_string()).transform(lon, lat)
    base.update(native_resolution_m=float(ds.res[0]), crs=ds.crs.to_string())
    b = ds.bounds
    if not (b.left <= x < b.right and b.bottom < y <= b.top):
        return Reading(status="outside_coverage", **base)
    r, c = ds.index(x, y)
    v = int(ds.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
    nd = ds.nodata
    if (nd is not None and v == nd) or (layer.value_kind == "class" and v == 0):
        return Reading(status="nodata", **base)
    if layer.value_kind == "count_of_n":
        return Reading(status="value", value=v, label=f"flagged flooded in {v} of {layer.n_scenes} scenes", **base)
    return Reading(status="value", value=v, label=(layer.legend or {}).get(v, f"code {v}"), **base)


# ---------------------------------------------------------------- vector lookups

@lru_cache(maxsize=4)
def _gdf(name: str) -> gpd.GeoDataFrame | None:
    p = current_dir() / name
    return gpd.read_parquet(p) if p.exists() else None


def _nearest(gdf: gpd.GeoDataFrame, lon: float, lat: float, max_m: float):
    utm = utm_for(lon, lat)
    pt = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(utm).iloc[0]
    # coarse prefilter in degrees (~max_m * 1.5) before projecting
    d = max_m / 111_000 * 1.5
    cand = gdf.cx[lon - d:lon + d, lat - d:lat + d]
    if cand.empty:
        return None, None
    dist = cand.to_crs(utm).distance(pt)
    i = dist.idxmin()
    return (cand.loc[i], float(dist.loc[i])) if dist.loc[i] <= max_m else (None, None)


from terrasense.config import load_assessment_rules  # noqa: E402

S4A_MAX_M = float(load_assessment_rules()["nearby_points"]["s4a_max_distance_m"])
GCP_MAX_M = float(load_assessment_rules()["nearby_points"]["wetland_gcp_max_distance_m"])


def nearest_s4a(lon: float, lat: float) -> Reading:
    base = dict(layer_id="s4a_field_nga", title=f"Soils4Africa field observation (nearest within {S4A_MAX_M:.0f} m)",
                theme="field_observation", measured=True, **_prov("s4a_field"),
                caveats=["Field description at an agricultural sampling plot; NOT co-located with your point unless distance≈0.",
                         "No laboratory texture in this release.", "Publisher: quality control still ongoing."])
    g = _gdf("s4a_field_nga.parquet")
    if g is None:
        return Reading(status="unavailable", **base)
    g = g[g.qc_reject_reason == ""]
    row, dist = _nearest(g, lon, lat, S4A_MAX_M)
    if row is None:
        return Reading(status="outside_coverage", **base)
    fields = {k: (None if (isinstance(row[k], float) and np.isnan(row[k])) else str(row[k]))
              for k in ["plot_code", "main_land_use", "bare_soil", "lndform", "slope_class", "srf_crust",
                        "crsfrgab", "depth_restriction_cause", "sign_of_erosion", "gully_erosion"]}
    return Reading(status="value", value=None, label="; ".join(f"{k}={v}" for k, v in fields.items() if v),
                   observation=str(row["survey_date"].date()) if row["survey_date"] is not None else None,
                   distance_m=round(dist, 1), **base)


def nearest_wetland_gcp(lon: float, lat: float) -> Reading:
    base = dict(layer_id="wetland_gcp_south_ng", title=f"Southern Nigeria wetland control point (nearest within {GCP_MAX_M:.0f} m)",
                theme="wetland_label", **_prov("wetland_south_ng"), observation="not recorded (study map year 2018)",
                caveats=["Point label from a published study; observation date not recorded.",
                         "The study's wetland MAP is not in the released archive, so no wall-to-wall wetland layer is available."])
    g = _gdf("wetland_gcp_south_ng.parquet")
    if g is None:
        return Reading(status="unavailable", **base)
    g = g[g.qc_reject_reason == ""]
    row, dist = _nearest(g, lon, lat, GCP_MAX_M)
    if row is None:
        return Reading(status="outside_coverage", **base)
    return Reading(status="value", value=int(row["class_code"]), label=str(row["class_name"]),
                   distance_m=round(dist, 1), **base)


def basin_lookup(lon: float, lat: float) -> list[Reading]:
    out = []
    for lev in ("06", "08"):
        base = dict(layer_id=f"hybas_lev{lev}", title=f"HydroBASINS v1c level {int(lev)}", theme="basin",
                    observation="static (HydroSHEDS v1, SRTM-derived)", native_resolution_m=None, historical=False,
                    **_prov("hydrobasins_af"),
                    caveats=["A drainage basin is a catchment area, not a wetland or flood zone."])
        g = _gdf(f"hybas_lev{lev}_nga.parquet")
        if g is None:
            out.append(Reading(status="unavailable", **base))
            continue
        hit = g[g.contains(Point(lon, lat))]
        if hit.empty:
            out.append(Reading(status="outside_coverage", **base))
            continue
        r = hit.iloc[0]
        out.append(Reading(status="value", value=int(r.HYBAS_ID),
                           label=(f"HYBAS_ID {int(r.HYBAS_ID)}; PFAF {int(r.PFAF_ID)}; sub-basin {r.SUB_AREA:,.0f} km²; "
                                  f"upstream {r.UP_AREA:,.0f} km²; next downstream {int(r.NEXT_DOWN)}; "
                                  f"{'endorheic' if r.ENDO else 'exorheic'}{'; coastal' if r.COAST else ''}"), **base))
    return out


def all_readings(lon: float, lat: float) -> list[Reading]:
    return ([sample_raster(l, lon, lat) for l in RASTER_LAYERS] + [wofs_reading(lon, lat)]
            + [nearest_s4a(lon, lat), nearest_wetland_gcp(lon, lat)] + basin_lookup(lon, lat))


# ---------------------------------------------------------------- SoilGrids (modelled prior)

SG_DIR_NAME = "soilgrids"
SG_DEPTHS = ("0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm")
SG_STATS = ("mean", "Q0.05", "Q0.5", "Q0.95")
SG_PROPS = ("sand", "silt", "clay")


def _sg_path(prop: str, depth: str, stat: str) -> Path:
    from terrasense.config import RAW_DIR
    return RAW_DIR / SG_DIR_NAME / f"{prop}_{depth}_{stat}.tif"


def soilgrids_profile(lon: float, lat: float) -> dict:
    """Modelled sand/silt/clay (%) per depth with 90% prediction interval. Never measured truth."""
    base = {"source_id": "soilgrids", "kind": "modelled", "native_resolution_m": 250.0,
            "crs": "Interrupted Goode Homolosine (ISRIC)", "model": "Quantile Regression Forest (SoilGrids 2.0)",
            "units": "percent (source g/kg ÷ 10)", **_prov("soilgrids"),
            "caveats": ["Modelled prediction at 250 m, not a measurement at this point.",
                        "Interval is the model's 5th–95th percentile, not a measured range.",
                        "Each statistic is predicted independently, so means need not sum to exactly 100 %.",
                        "Training data (WoSIS) are sparse in Nigeria; local accuracy is unknown."]}
    if not _sg_path("sand", "0-5cm", "Q0.5").exists():
        return {"status": "unavailable", "depths": [], **base}
    depths = []
    for depth in SG_DEPTHS:
        row = {"depth": depth}
        complete = True
        for prop in SG_PROPS:
            vals = {}
            for stat in SG_STATS:
                p = _sg_path(prop, depth, stat)
                if not p.exists():
                    complete = False
                    continue
                ds = _open(str(p))
                x, y = _sg_tx(ds).transform(lon, lat)
                b = ds.bounds
                if not (b.left <= x < b.right and b.bottom < y <= b.top):
                    complete = False
                    continue
                r, c = ds.index(x, y)
                v = int(ds.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
                vals[stat] = None if v == ds.nodata else round(v / 10, 1)
            row[prop] = vals
        if not complete:
            row["status"] = "incomplete"
        elif any(v is None for p in SG_PROPS for v in row[p].values()):
            row["status"] = "nodata"
        else:
            row["status"] = "value"
            row["sum_of_means_pct"] = round(sum(row[p]["mean"] for p in SG_PROPS), 1)
        depths.append(row)
    status = "value" if any(d["status"] == "value" for d in depths) else "nodata"
    return {"status": status, "depths": depths, **base}


@lru_cache(maxsize=4)
def _sg_tx_cached(wkt: str):
    return Transformer.from_crs("EPSG:4326", wkt, always_xy=True)


def _sg_tx(ds):
    return _sg_tx_cached(ds.crs.to_wkt())


# ---------------------------------------------------------------- DE Africa WOfS all-time summary

WOFS_PERIOD = "1984-01-01 to 2025-12-31 (Landsat 5/7/8/9)"


def wofs_reading(lon: float, lat: float) -> Reading:
    from terrasense.config import RAW_DIR
    from terrasense.ingest.wofs import OUT, PERIOD, PRODUCT, tile_of
    base = dict(layer_id="deafrica_wofs_alltime", title="DE Africa WOfS all-time water observation frequency",
                theme="water_frequency", observation=WOFS_PERIOD, native_resolution_m=30.0, crs="EPSG:6933",
                **_prov("deafrica_wofs"),
                caveats=["Fraction of cloud-free Landsat observations classified as water — historical, not current.",
                         "Single detections can be misclassification (cloud shadow, terrain shadow, dark surfaces).",
                         "Says nothing about depth, flow or ground bearing capacity."])
    x, y = _tx("EPSG:6933").transform(lon, lat)
    ix, iy = tile_of(x, y)
    stem = OUT / f"x{ix:03d}y{iy:03d}" / f"{PRODUCT}_x{ix:03d}y{iy:03d}_{PERIOD}"
    pw, pc = Path(f"{stem}_count_wet.tif"), Path(f"{stem}_count_clear.tif")
    if not (pw.exists() and pc.exists()):
        return Reading(status="unavailable", **base)
    vals = []
    for p in (pw, pc):
        ds = _open(str(p))
        r, c = ds.index(x, y)
        v = int(ds.read(1, window=((r, r + 1), (c, c + 1)))[0, 0])
        vals.append(None if (ds.nodata is not None and v == ds.nodata) else v)
    wet, clear = vals
    if wet is None or clear is None or clear == 0:
        return Reading(status="nodata", label=f"no clear observations (clear={clear})", **base)
    return Reading(status="value", value=round(wet / clear, 4), counts={"wet": wet, "clear": clear},
                   label=f"water in {wet} of {clear} clear observations ({100 * wet / clear:.1f} %)", **base)
