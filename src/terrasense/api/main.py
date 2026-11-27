"""FastAPI service. Run: uvicorn terrasense.api.main:app --reload"""
from __future__ import annotations

import json
from datetime import date

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from terrasense import __version__
from terrasense.assessment.engine import TRAFFICABILITY_MODEL_ENABLED, OutsideNigeria, assess
from terrasense.config import ARTIFACTS_DIR, load_registry
from terrasense.geo.boundary import BoundaryUnavailable
from terrasense.geo.layers import RASTER_LAYERS, basin_lookup, current_dir

from .schemas import AssessRequest, AssessResponse, ReadingOut

app = FastAPI(title="TerraSense Nigeria (research prototype)", version=__version__,
              description="Evidence lookup for locations in Nigeria. Never a safety or trafficability certification.")

ALLOWED_IMAGE = {"image/jpeg", "image/png"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG\r\n\x1a\n": "image/png"}


def _run(lat: float, lon: float, d: date | None, image_meta: dict | None = None) -> dict:
    try:
        return assess(lat, lon, d, image_meta)
    except OutsideNigeria as e:
        raise HTTPException(status_code=422, detail=str(e))
    except BoundaryUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/health")
def health():
    d = current_dir()
    return {"status": "ok" if d.exists() else "degraded", "version": __version__,
            "data_version": d.name if d.exists() else None,
            "layers_present": {l.id: l.path.exists() for l in RASTER_LAYERS}}


@app.get("/sources")
def sources():
    reg = load_registry()
    keep = ("id", "title", "doi", "url", "licence", "attribution", "kind", "measured", "role", "verified", "status", "notes")
    return {"boundary": {k: reg["boundary"].get(k) for k in ("id", "title", "url", "licence", "attribution")},
            "sources": [{k: s.get(k) for k in keep} for s in reg["sources"]]}


@app.get("/models")
def models():
    p = ARTIFACTS_DIR / "models" / "registry.json"
    trained = json.loads(p.read_text()) if p.exists() else []
    return {"trained_models": trained,
            "trafficability_model_enabled": TRAFFICABILITY_MODEL_ENABLED,
            "not_trained": {
                "soil_texture_regressor": "blocked: no measured, georeferenced Nigerian sand/silt/clay available",
                "surface_segmentation": "blocked: no Nigerian labelled imagery with independent test sites ingested",
                "wetland_classifier": "pending: wetland control points exist but date-matched imagery not yet ingested",
                "trafficability": "disabled: no paired soil/vehicle/outcome data or expert validation"}}


@app.post("/assess", response_model=AssessResponse)
def assess_json(req: AssessRequest):
    return _run(req.lat, req.lon, req.date)


@app.post("/assess/image", response_model=AssessResponse)
async def assess_with_image(lat: float = Form(..., ge=-90, le=90), lon: float = Form(..., ge=-180, le=180),
                            date_: str | None = Form(None, alias="date"), image: UploadFile = File(...)):
    try:
        d = AssessRequest(lat=lat, lon=lon, date=date_).date
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="image larger than 10 MB")
    sniffed = next((t for m, t in MAGIC.items() if data.startswith(m)), None)
    if image.content_type not in ALLOWED_IMAGE or sniffed is None or sniffed != image.content_type:
        raise HTTPException(status_code=415, detail="unsupported file: only JPEG or PNG images are accepted")
    return _run(lat, lon, d, {"filename": image.filename, "content_type": sniffed, "bytes": len(data), "analysed": False})


@app.get("/basin", response_model=list[ReadingOut])
def basin(lat: float, lon: float):
    try:
        from terrasense.assessment.engine import validate_point
        validate_point(lat, lon)
    except OutsideNigeria as e:
        raise HTTPException(status_code=422, detail=str(e))
    return [r.as_dict() for r in basin_lookup(lon, lat)]
