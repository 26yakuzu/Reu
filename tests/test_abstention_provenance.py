"""Abstention, hazard and temporal-provenance rules, on real processed data where present."""
import json
import re
from datetime import date

from terrasense.assessment.engine import FLOODWATER_WARNING, STATES, assess, equipment_panel, soil_composition_panel
from terrasense.geo.layers import Reading

from .conftest import needs_processed

FORBIDDEN = re.compile(r"\bsafe to (drive|cross)\b|\bprobabilit|\bpassable\b|\bgo ahead\b|\bload limit of\b", re.I)


def _r(**kw):
    base = dict(layer_id="x", title="t", theme="flood_history", status="value", observation="2022")
    base.update(kw)
    return Reading(**base)


def test_no_evidence_means_abstain():
    eq = equipment_panel([_r(status="unavailable", value=None)], soil_composition_panel())
    assert {e["state"] for e in eq} == {"insufficient_evidence"}
    assert all("inspection" in e["recommendation"].lower() for e in eq)


def test_flood_history_is_hazard_with_floodwater_warning():
    eq = equipment_panel([_r(value=1, label="Flooded at least once")], soil_composition_panel())
    assert {e["state"] for e in eq} == {"observed_environmental_hazard"}
    assert all(FLOODWATER_WARNING in e["warnings"] for e in eq)


def test_states_are_from_allowed_set():
    for rs in ([], [_r(value=0)], [_r(value=1)], [_r(theme="water", value=1)]):
        assert {e["state"] for e in equipment_panel(rs, soil_composition_panel())} <= set(STATES)


def test_soil_never_fabricated():
    s = soil_composition_panel()
    assert s["status"] == "unavailable" and s["sand_pct"] is s["silt_pct"] is s["clay_pct"] is None


@needs_processed
def test_real_points_provenance_and_language():
    for lat, lon in [(12.4093, 10.0458), (6.60, 3.35), (9.08, 7.40)]:
        res = assess(lat, lon, date(2024, 1, 1))
        txt = json.dumps(res)
        assert not FORBIDDEN.search(txt), FORBIDDEN.search(txt)
        assert res["trafficability_model_enabled"] is False
        assert any("2024-01-01" in w for w in res["warnings"])
        for sec in ("visible_terrain", "water_and_wetland", "basin", "field_observations"):
            for r in res[sec]:
                assert r["status"] in ("value", "nodata", "outside_coverage", "unavailable")
                if r["status"] == "value":
                    assert r["observation"], r["layer_id"]          # temporal provenance required
                    assert r["source_id"] and r["licence"], r["layer_id"]
                    if r["theme"] != "basin" and r["theme"] != "field_observation" and r["theme"] != "wetland_label":
                        assert r["native_resolution_m"] and r["crs"], r["layer_id"]


@needs_processed
def test_hadejia_flood_point_is_hazard_lagos_abstains():
    h = assess(12.4093, 10.0458)
    assert h["assessment_status"] == "observed_environmental_hazard"
    lg = assess(9.08, 7.40)   # Abuja: no local layers beyond basin
    assert lg["assessment_status"] == "abstain_insufficient_evidence"
    assert lg["data_quality"]["any_local_evidence_beyond_basin"] is False
