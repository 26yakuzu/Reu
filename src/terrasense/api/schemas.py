from __future__ import annotations

import datetime as _dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Status = Literal["value", "nodata", "outside_coverage", "unavailable"]
EquipState = Literal["not_assessed", "insufficient_evidence", "observed_environmental_hazard",
                     "preliminary_requires_expert_review"]


class AssessRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="WGS84 latitude", examples=[12.4093])
    lon: float = Field(..., ge=-180, le=180, description="WGS84 longitude", examples=[10.0458])
    date: _dt.date | None = Field(None, description="Optional date of interest (ISO 8601). Must not be in the future.")

    @field_validator("date")
    @classmethod
    def not_future(cls, v):
        if v is not None and v > _dt.date.today():
            raise ValueError("date is in the future")
        if v is not None and v.year < 1984:
            raise ValueError("date precedes the satellite record used by this project (1984)")
        return v

    model_config = {"json_schema_extra": {"examples": [
        {"lat": 12.4093, "lon": 10.0458, "date": "2022-09-20"},
        {"lat": 6.60, "lon": 3.35},
    ]}}


class ReadingOut(BaseModel):
    layer_id: str
    title: str
    theme: str
    status: Status
    value: float | int | None = None
    label: str | None = None
    source_id: str | None = None
    doi: str | None = None
    licence: str | None = None
    observation: str | None = None
    native_resolution_m: float | None = None
    crs: str | None = None
    measured: bool
    historical: bool
    distance_m: float | None = None
    caveats: list[str]


class EquipmentOut(BaseModel):
    equipment: str
    label: str
    state: EquipState
    observed_hazards: list[str]
    evidence_gaps: list[str]
    recommendation: str
    warnings: list[str]


class SoilOut(BaseModel):
    status: Literal["value", "unavailable"]
    sand_pct: float | None
    silt_pct: float | None
    clay_pct: float | None
    depth_cm: str | None
    interval: str | None
    reason: str
    next_step: str


class AssessResponse(BaseModel):
    query: dict
    assessment_status: Literal["abstain_insufficient_evidence", "observed_environmental_hazard",
                               "preliminary_requires_expert_review"]
    generated_at: str
    software_version: str
    data_version: str
    visible_terrain: list[ReadingOut]
    water_and_wetland: list[ReadingOut]
    basin: list[ReadingOut]
    field_observations: list[ReadingOut]
    soil_composition: SoilOut
    equipment_screening: list[EquipmentOut]
    trafficability_model_enabled: bool
    data_quality: dict
    warnings: list[str]
    recommendation: str
