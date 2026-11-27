# Architecture

```
configs/sources.yaml ──► ingest.fetch ──► data/raw/<source>/ (immutable, checksummed)
                                         │
                         ingest.extract ─┤ (safe unzip → extracted/)
                                         │
                         ingest.audit ───┼──► artifacts/reports/audit.json, docs/data_dictionary/AUDIT.md
                                         │
                         ingest.prepare ─┴──► data/processed/<version>/  (uint8 COG, GeoParquet)
                                                      │                    + artifacts/manifests/processed_<v>.json
                                                      ▼
                         geo.layers  (point lookups: value | nodata | outside_coverage | unavailable)
                                                      │
                         assessment.engine (Nigeria check → readings → hazard/abstention rules)
                                   │                                   │
                         api.main (FastAPI)                     app/streamlit_app.py
```

Design rules:

- **Raw data is immutable.** Processing is versioned (`PREP_VERSION`) and every output is sha256-hashed.
- **Native CRS and resolution are kept.** Rasters are re-encoded losslessly, never resampled. Display
  overlays are reprojected separately and are never queried for values.
- **Boundary filtering uses a polygon.** Point-in-polygon on the geoBoundaries ADM0, never a bounding box.
- **Absent data stays absent.** It is reported as `unavailable` and never filled.
- **Nearby points are not your point.** Point data (S4A, wetland GCPs) is shown only within a fixed
  radius (1 km / 250 m), always with its distance.
- **No LLM in the core path.** An optional explanation layer may only paraphrase the structured output.

Later upgrades: PostgreSQL/PostGIS for the layer store, a React/Leaflet frontend, and DE Africa STAC
ingestion (WOfS, S1, S2).
