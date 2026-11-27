import io

import pytest
from fastapi.testclient import TestClient

from terrasense.api.main import app

from .conftest import needs_boundary, needs_processed

c = TestClient(app)
PNG_1PX = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
           b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def test_health_and_sources():
    assert c.get("/health").status_code == 200
    s = c.get("/sources").json()
    ids = {x["id"] for x in s["sources"]}
    assert {"s4a_field", "ozoro_texture", "hadejia_flood", "hydrobasins_af"} <= ids
    assert all("licence" in x for x in s["sources"])


def test_models_trafficability_disabled():
    m = c.get("/models").json()
    assert m["trafficability_model_enabled"] is False
    assert "soil_texture_regressor" in m["not_trained"]


@pytest.mark.parametrize("body", [{"lat": 95, "lon": 8}, {"lat": 9, "lon": 200}, {"lat": "x", "lon": 8},
                                  {"lat": 9, "lon": 8, "date": "2030-01-01"}, {"lat": 9, "lon": 8, "date": "1970-01-01"},
                                  {"lat": 9, "lon": 8, "date": "not-a-date"}, {"lon": 8}])
def test_invalid_inputs_rejected(body):
    assert c.post("/assess", json=body).status_code == 422


@needs_boundary
@pytest.mark.parametrize("lat,lon", [(6.37, 2.42), (13.51, 2.11), (48.86, 2.35), (3.5, 5.0)])
def test_outside_nigeria_rejected(lat, lon):
    r = c.post("/assess", json={"lat": lat, "lon": lon})
    assert r.status_code == 422 and "outside Nigeria" in r.json()["detail"]


@needs_processed
def test_unsupported_file_rejected():
    files = {"image": ("evil.png", io.BytesIO(b"#!/bin/sh\necho hi"), "image/png")}
    assert c.post("/assess/image", data={"lat": 9.08, "lon": 7.4}, files=files).status_code == 415
    files = {"image": ("doc.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
    assert c.post("/assess/image", data={"lat": 9.08, "lon": 7.4}, files=files).status_code == 415


@needs_processed
def test_image_accepted_but_not_analysed():
    files = {"image": ("site.png", io.BytesIO(PNG_1PX), "image/png")}
    r = c.post("/assess/image", data={"lat": 9.08, "lon": 7.4}, files=files)
    assert r.status_code == 200
    j = r.json()
    assert j["query"]["image"]["analysed"] is False
    assert any("NOT analysed" in w for w in j["warnings"])
    assert j["soil_composition"]["sand_pct"] is None


@needs_processed
def test_basin_endpoint():
    r = c.get("/basin", params={"lat": 9.08, "lon": 7.4})
    assert r.status_code == 200 and r.json()[0]["status"] == "value"
    assert c.get("/basin", params={"lat": 6.37, "lon": 2.42}).status_code == 422


def test_openapi_has_examples():
    spec = c.get("/openapi.json").json()
    assert "/assess" in spec["paths"]
    assert "examples" in str(spec["components"]["schemas"]["AssessRequest"])


def test_models_endpoint_reports_wetland_honestly():
    m = c.get("/models").json()
    w = [t for t in m["trained_models"] if t["id"] == "wetland_rf_geomad2018"]
    if not w:
        pytest.skip("wetland model not trained in this checkout")
    w = w[0]
    assert set(w["classes"]) == {"open_water", "vegetated_wetland", "other"}
    assert "baseline_rule_wofs_mndwi" in w["baselines_macro_f1"]
    assert "pre-registered" in w["deployment_gate"]["rule"]
