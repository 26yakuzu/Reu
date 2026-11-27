# TerraSense Nigeria

A research prototype for civilian environmental evidence lookup in Nigeria: visible terrain, soil context,
historical flood and water extent, drainage basins, and a preliminary qualitative equipment screening.

> **It is not a safety, trafficability or engineering certification.** Every mapped layer is historical.
> TerraSense never says a location is safe to drive. It never gives crossing probabilities, load limits or
> routes, and it never recommends entering floodwater. When evidence is missing, it abstains and recommends
> inspection by a qualified engineer.

Current status (Stages 0–2, plus API/tests): see [`docs/research/GAP_REPORT.md`](docs/research/GAP_REPORT.md).
**No ML model has been trained.** The audit showed that no eligible Nigerian measured-texture or labelled-imagery
data is available yet.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock.txt && pip install -e ".[app,dev]" --no-deps
cp .env.example .env   # optional; nothing secret is required
```

## Data pipeline (needs network access to the hosts listed in `configs/sources.yaml`)

```bash
python -I scripts/fetch.py --include-large   # ~430 MB, verifies Zenodo md5 / Mendeley sha256
python -I scripts/extract.py                 # safe extraction into data/raw/*/extracted (~1.5 GB)
python -I scripts/audit.py                   # Stage 1 audit -> artifacts/reports/audit.json, docs/data_dictionary/AUDIT.md
python -I scripts/prepare.py                 # lossless uint8 COGs + GeoParquet -> data/processed/<version>/
```

Raw files are never modified. Checksums go to `artifacts/manifests/raw_manifest.json`. Processed files
are versioned and hashed in `artifacts/manifests/processed_<version>.json`.

## Run

```bash
uvicorn terrasense.api.main:app --reload            # API docs at http://127.0.0.1:8000/docs
streamlit run app/streamlit_app.py                   # dashboard at http://localhost:8501
python -m pytest -q                                  # tests (real-data tests skip if data are absent)
```

Example request:

```bash
curl -s -X POST localhost:8000/assess -H 'content-type: application/json' -d '{"lat":12.4093,"lon":10.0458,"date":"2022-09-20"}'
```

## Training / evaluation

`scripts/train.py` and `scripts/evaluate.py` currently refuse to run and print the blocker for each
candidate model (see the gap report). The spatial-block split and leakage check that any future
model must pass are in `src/terrasense/models/splits.py`.

## Layout

```
configs/sources.yaml       verified source registry (URLs, licences, checksums, eligibility notes)
scripts/                   fetch / extract / audit / prepare / train / evaluate entry points
src/terrasense/ingest      download, extraction, audit, preprocessing
src/terrasense/geo         Nigeria boundary, CRS helpers, point lookups on processed layers
src/terrasense/assessment  evidence assembly + abstention / hazard rules
src/terrasense/models      spatial splits + leakage checks (no trained models yet)
src/terrasense/api         FastAPI service
app/                       Streamlit dashboard
tests/                     unit + synthetic integration tests
docs/                      gap report, data dictionary, limitations, architecture, model cards, user guide
artifacts/                 manifests and reports (no raw data)
```

## Data attribution

All datasets used are CC BY 4.0 unless noted. Full citations are in `configs/sources.yaml` and the
dashboard's *Sources* tab. Boundary: geoBoundaries (Runfola et al. 2020), GRID3 source. Basins:
HydroBASINS (Lehner & Grill 2013).
