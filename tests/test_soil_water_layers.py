"""SoilGrids (modelled) and WOfS readers on SYNTHETIC rasters, plus real-data checks when present."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

import terrasense.config as cfg
import terrasense.geo.layers as layers
import terrasense.ingest.wofs as wofs
from terrasense.assessment.engine import equipment_panel, soil_composition_panel
from terrasense.config import RAW_DIR



def _write(path, arr, crs, transform, nodata, dtype):
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype=dtype,
                       crs=crs, transform=transform, nodata=nodata) as ds:
        ds.write(arr.astype(dtype), 1)


@pytest.fixture
def synthetic_raw(tmp_path, monkeypatch):
    raw = tmp_path / "SYNTHETIC_raw"
    monkeypatch.setattr(cfg, "RAW_DIR", raw)
    monkeypatch.setattr(wofs, "OUT", raw / "deafrica_wofs")
    layers._open.cache_clear()
    yield raw
    layers._open.cache_clear()


def test_soilgrids_units_interval_and_sum(synthetic_raw):
    # SYNTHETIC: constant g/kg grids in EPSG:4326 around lon 7.5, lat 9.0
    tr = from_origin(7.0, 9.5, 0.01, 0.01)
    vals = {"sand": {"mean": 600, "Q0.05": 400, "Q0.5": 610, "Q0.95": 800},
            "silt": {"mean": 150, "Q0.05": 80, "Q0.5": 140, "Q0.95": 260},
            "clay": {"mean": 250, "Q0.05": 120, "Q0.5": 240, "Q0.95": 400}}
    for prop, st in vals.items():
        for depth in layers.SG_DEPTHS:
            for stat, v in st.items():
                _write(synthetic_raw / "soilgrids" / f"{prop}_{depth}_{stat}.tif", np.full((100, 100), v),
                       "EPSG:4326", tr, -32768, "int16")
    prof = layers.soilgrids_profile(7.5, 9.0)
    top = prof["depths"][0]
    assert prof["status"] == "value" and prof["kind"] == "modelled"
    assert top["sand"] == {"mean": 60.0, "Q0.05": 40.0, "Q0.5": 61.0, "Q0.95": 80.0}   # g/kg -> %
    assert top["sum_of_means_pct"] == 100.0
    soil = soil_composition_panel(7.5, 9.0)
    assert soil["status"] == "modelled_only"
    assert soil["sand_pct"] is None and soil["measured"]["status"] == "unavailable"
    # modelled soil must NOT upgrade equipment screening
    eq = equipment_panel([], soil)
    assert {e["state"] for e in eq} == {"insufficient_evidence"}
    assert "only modelled" in eq[0]["evidence_gaps"][0]
    # outside the synthetic grid -> incomplete, never filled
    assert layers.soilgrids_profile(12.0, 12.0)["status"] == "nodata"


def test_wofs_frequency_and_nodata(synthetic_raw):
    from pyproj import Transformer
    lon, lat = 7.5, 9.0
    x, y = Transformer.from_crs(4326, 6933, always_xy=True).transform(lon, lat)
    ix, iy = wofs.tile_of(x, y)
    left, bottom, right, top = wofs.tile_bounds(ix, iy)
    stem = synthetic_raw / "deafrica_wofs" / f"x{ix:03d}y{iy:03d}" / f"{wofs.PRODUCT}_x{ix:03d}y{iy:03d}_{wofs.PERIOD}"
    tr = from_origin(left, top, 30 * 32, 30 * 32)       # SYNTHETIC coarse 100x100 tile
    wet = np.full((100, 100), 30)
    clear = np.full((100, 100), 400)
    c, r = int((x - left) // (30 * 32)), int((top - y) // (30 * 32))
    clear[r, c + 1] = 0
    _write(stem.with_name(stem.name + "_count_wet.tif"), wet, "EPSG:6933", tr, None, "int16")
    _write(stem.with_name(stem.name + "_count_clear.tif"), clear, "EPSG:6933", tr, None, "int16")
    rd = layers.wofs_reading(lon, lat)
    assert rd.status == "value" and rd.value == pytest.approx(0.075) and "30 of 400" in rd.label
    rd2 = layers.wofs_reading(*Transformer.from_crs(6933, 4326, always_xy=True).transform(left + (c + 1.5) * 960, top - (r + 0.5) * 960))
    assert rd2.status == "nodata"


def test_tile_index_matches_publisher_stac():
    # verified against wofs_ls_summary_alltime_x154y096 STAC proj:transform (-2592000, 1920000)
    assert wofs.tile_bounds(154, 96) == (-2592000, 1824000, -2496000, 1920000)
    assert wofs.tile_of(-2591999, 1919999) == (154, 96)


@pytest.mark.skipif(len(list((RAW_DIR / "soilgrids").glob("*.tif"))) < 72 if (RAW_DIR / "soilgrids").exists() else True,
                    reason="SoilGrids not fully fetched (72 layers)")
def test_real_soilgrids_values_plausible():
    prof = layers.soilgrids_profile(7.49, 9.06)  # Abuja
    d = next(x for x in prof["depths"] if x["status"] == "value")
    for p in ("sand", "silt", "clay"):
        q = d[p]
        assert 0 <= q["Q0.05"] <= q["Q0.5"] <= q["Q0.95"] <= 100
