"""Evidence assembly and research-only qualitative screening.

Hard rules (enforced here and tested):
* Never output a crossing probability, load threshold, route or "safe" verdict.
* Allowed per-equipment states: not_assessed, insufficient_evidence,
  observed_environmental_hazard, preliminary_requires_expert_review.
* Any historical flood / water evidence => observed_environmental_hazard plus the
  instruction never to enter floodwater.
* Missing measured soil evidence => insufficient_evidence (abstain) and a
  recommendation for qualified site inspection.
* The supervised trafficability module is DISABLED: no paired soil/vehicle/outcome
  data exist (see docs/limitations).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from terrasense import __version__
from terrasense.geo.boundary import nigeria
from terrasense.geo.layers import Reading, all_readings, current_dir

EQUIPMENT = {
    "passenger_car": "Ordinary passenger car",
    "pickup_4x4": "Pickup / 4x4",
    "agricultural_tractor": "Agricultural tractor",
    "construction_truck": "Construction truck",
}
STATES = ("not_assessed", "insufficient_evidence", "observed_environmental_hazard", "preliminary_requires_expert_review")
TRAFFICABILITY_MODEL_ENABLED = False

FLOODWATER_WARNING = ("Never drive into or through floodwater. Historical maps cannot show current water depth, "
                      "current flow or road condition.")
INSPECTION = "Arrange inspection by a qualified geotechnical / civil engineer before any vehicle or equipment use."
DISCLAIMER = ("Research prototype. Not a safety, trafficability or engineering certification. "
              "All mapped layers are historical; none represent current conditions.")


class OutsideNigeria(ValueError):
    pass


def validate_point(lat: float, lon: float) -> str | None:
    b = nigeria()
    if not b.contains([lon], [lat])[0]:
        raise OutsideNigeria(f"({lat}, {lon}) is outside Nigeria (geoBoundaries ADM0). TerraSense covers Nigeria only.")
    return b.state_of(lon, lat)


def _hazards(readings: list[Reading]) -> list[str]:
    out = []
    for r in readings:
        if r.status != "value":
            continue
        if r.theme == "flood_history" and r.value and r.value > 0:
            out.append(f"{r.title}: {r.label} [{r.observation}]")
        if r.theme == "water" and r.value == 1:
            out.append(f"{r.title}: {r.label} [{r.observation}]")
        if r.theme == "visible_surface" and r.label and r.label.startswith("Water"):
            out.append(f"{r.title}: mapped as water [{r.observation}]")
        if r.theme == "wetland_label" and r.label and any(k in r.label.lower() for k in ("water", "swamp", "marsh", "mangrove")):
            out.append(f"{r.title}: labelled '{r.label}' {r.distance_m} m away")
    return out


def soil_composition_panel() -> dict:
    return {"status": "unavailable",
            "sand_pct": None, "silt_pct": None, "clay_pct": None, "depth_cm": None, "interval": None,
            "reason": ("No eligible measured, georeferenced sand/silt/clay data for Nigeria is available to this "
                       "project: Soils4Africa lab results are not downloadable; the Ozoro dataset has no coordinates "
                       "(50 aggregated rows, jar test). Modelled SoilGrids/iSDAsoil layers are not yet ingested."),
            "next_step": "Ingest SoilGrids 250 m (modelled, with Q05/Q95) as a clearly-labelled prior."}


def equipment_panel(readings: list[Reading], soil: dict) -> list[dict]:
    hazards = _hazards(readings)
    measured_soil = soil["status"] == "value"
    gaps = []
    if not measured_soil:
        gaps.append("no measured soil texture/strength at this location")
    gaps += ["no current (live) water or flood observation", "no slope/DEM layer ingested",
             "no validated vehicle–terrain outcome data (trafficability model disabled)"]
    out = []
    for key, name in EQUIPMENT.items():
        if hazards:
            state = "observed_environmental_hazard"
        elif not measured_soil:
            state = "insufficient_evidence"
        else:
            state = "preliminary_requires_expert_review"
        assert state in STATES
        out.append({"equipment": key, "label": name, "state": state, "observed_hazards": hazards,
                    "evidence_gaps": gaps, "recommendation": INSPECTION,
                    "warnings": [FLOODWATER_WARNING] if hazards else []})
    return out


def assess(lat: float, lon: float, query_date: date | None = None, image_meta: dict | None = None) -> dict:
    state = validate_point(lat, lon)
    readings = all_readings(lon, lat)
    soil = soil_composition_panel()
    equipment = equipment_panel(readings, soil)
    warnings = [DISCLAIMER]
    if query_date:
        warnings.append(f"You asked about {query_date.isoformat()}. No layer in this prototype is observed on that date; "
                        "all readings below carry their own observation period.")
    if image_meta:
        warnings.append("Photo received but NOT analysed: no image model validated on Nigerian labelled imagery exists "
                        "in this prototype. A photo can never establish soil composition or strength.")
    missing = [r.layer_id for r in readings if r.status in ("unavailable",)]
    out_cov = [r.layer_id for r in readings if r.status == "outside_coverage"]
    any_value = any(r.status == "value" for r in readings if r.theme != "basin")
    overall = "abstain_insufficient_evidence" if all(e["state"] == "insufficient_evidence" for e in equipment) else (
        "observed_environmental_hazard" if any(e["state"] == "observed_environmental_hazard" for e in equipment)
        else "preliminary_requires_expert_review")
    return {
        "query": {"lat": lat, "lon": lon, "date": query_date.isoformat() if query_date else None,
                  "admin1": state, "image": image_meta},
        "assessment_status": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "software_version": __version__, "data_version": current_dir().name,
        "visible_terrain": [r.as_dict() for r in readings if r.theme == "visible_surface"],
        "water_and_wetland": [r.as_dict() for r in readings if r.theme in ("flood_history", "water", "wetland_label")],
        "basin": [r.as_dict() for r in readings if r.theme == "basin"],
        "field_observations": [r.as_dict() for r in readings if r.theme == "field_observation"],
        "soil_composition": soil,
        "equipment_screening": equipment,
        "trafficability_model_enabled": TRAFFICABILITY_MODEL_ENABLED,
        "data_quality": {"layers_with_value": [r.layer_id for r in readings if r.status == "value"],
                         "layers_nodata": [r.layer_id for r in readings if r.status == "nodata"],
                         "layers_outside_coverage": out_cov, "layers_unavailable": missing,
                         "any_local_evidence_beyond_basin": any_value},
        "warnings": warnings,
        "recommendation": INSPECTION,
    }
