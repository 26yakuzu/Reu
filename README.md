# TerraSense Nigeria

A research prototype for civilian environmental evidence lookup in Nigeria: visible terrain, soil context,
historical flood and water extent, drainage basins, and a preliminary qualitative equipment screening.

> **It is not a safety, trafficability or engineering certification.** Every mapped layer is historical.
> TerraSense never says a location is safe to drive. It never gives crossing probabilities, load limits or
> routes, and it never recommends entering floodwater. When evidence is missing, it abstains and recommends
> inspection by a qualified engineer.

Current status: see [`docs/research/GAP_REPORT.md`](docs/research/GAP_REPORT.md).
Soil texture, image and trafficability models are **not trained**: no eligible Nigerian measured-texture,
labelled-imagery or outcome data exist. One research model (a wetland/open-water classifier) is trained
with spatial-block evaluation; see its model card for results and whether it passed its deployment gate.

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
python -I scripts/fetch_wofs.py              # DE Africa WOfS 1984-2025, 131 tiles (~1.2 GB), publisher sha1 verified
python -I scripts/fetch_soilgrids.py         # SoilGrids 250 m, 72 layers over Nigeria via WCS (~1.4 GB, ~30-60 min)
python -I scripts/prepare.py                 # lossless uint8 COGs + GeoParquet + WOfS display mosaic -> data/processed/<version>/
python -I scripts/audit.py                   # re-run after all fetches so the audit covers WOfS and SoilGrids
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

```bash
python -I scripts/train.py --model wetland   # GeoMAD 2018 features (remote, checkpointed) -> baselines -> RF -> held-out test
python -I scripts/evaluate.py                # per-class P/R/F1, IoU, confusion matrices, by-state accuracy, gate
python -I scripts/train.py                   # lists blocked models and why
```

The spatial-block split and leakage check are in `src/terrasense/models/splits.py`. Precautionary screening
rules (e.g. the WOfS hazard threshold) are in `configs/assessment.yaml`.

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
