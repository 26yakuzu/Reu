"""End-to-end path on EXPLICITLY SYNTHETIC fixtures (offline).

Nothing here is evidence about Nigeria: the 'boundary' is an arbitrary square and
the flood raster is a made-up half-flooded grid. These fixtures only exercise code
paths and are never used for training or reported results.
"""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

import terrasense.assessment.engine as engine
import terrasense.geo.layers as layers
from terrasense.geo.boundary import Boundary


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    d = tmp_path / "SYNTHETIC_processed"
    d.mkdir()
    # SYNTHETIC flood raster in UTM 32N around lon 7.5, lat 9.0; west half = 1, east half = 0
    arr = np.zeros((100, 100), np.uint8)
    arr[:, :50] = 1
    with rasterio.open(d / "hadejia_flood_extent_2022.tif", "w", driver="GTiff", height=100, width=100, count=1,
                       dtype="uint8", crs="EPSG:32632", transform=from_origin(550_000, 996_000, 30, 30), nodata=255) as ds:
        ds.write(arr, 1)
    syn_boundary = Boundary(box(5.0, 8.0, 10.0, 10.0), None, source="SYNTHETIC_square")
    monkeypatch.setattr(layers, "current_dir", lambda: d)
    monkeypatch.setattr(engine, "current_dir", lambda: d)
    monkeypatch.setattr(engine, "nigeria", lambda: syn_boundary)
    layers._gdf.cache_clear()
    layers._open.cache_clear()
    yield d
    layers._gdf.cache_clear()
    layers._open.cache_clear()


def _lonlat(x, y):
    from pyproj import Transformer
    return Transformer.from_crs(32632, 4326, always_xy=True).transform(x, y)


def test_synthetic_end_to_end(synthetic):
    lon_w, lat_w = _lonlat(550_000 + 15 * 30, 996_000 - 50 * 30)   # flooded half
    lon_e, lat_e = _lonlat(550_000 + 85 * 30, 996_000 - 50 * 30)   # dry half
    w = engine.assess(lat_w, lon_w)
    e = engine.assess(lat_e, lon_e)
    fw = {r["layer_id"]: r for r in w["water_and_wetland"]}
    assert fw["hadejia_flood_extent_2022"]["status"] == "value" and fw["hadejia_flood_extent_2022"]["value"] == 1
    assert w["assessment_status"] == "observed_environmental_hazard"
    assert e["assessment_status"] == "abstain_insufficient_evidence"
    # files that were not created are reported as unavailable, never filled
    assert "hadejia_flood_extent_2020" in w["data_quality"]["layers_unavailable"]
    assert "hybas_lev06" in w["data_quality"]["layers_unavailable"]
    far = engine.assess(9.9, 9.9)
    assert {r["status"] for r in far["water_and_wetland"]} <= {"outside_coverage", "unavailable"}


def test_synthetic_outside_boundary(synthetic):
    with pytest.raises(engine.OutsideNigeria):
        engine.assess(12.0, 12.0)
