# Stage 0–1 gap report

Date: 2026-11-27 · Reproduce with `python -I scripts/audit.py` (writes `artifacts/reports/audit.json`
and `docs/data_dictionary/AUDIT.md`). All numbers below come from that audit of the actual files.

## Stage 0 — workspace and access

| item | finding |
|---|---|
| Repository | Empty except LICENSE (BSL-1.0) and a stub README. |
| Runtime | Python 3.13 in the cloud container (the project targets ≥3.11). Geospatial stack installs from PyPI (GDAL comes bundled in the rasterio/pyogrio wheels). No QGIS. |
| Network | At first only package registries were reachable; every data host returned proxy 403. After approval, a personal environment `Reu` now allows Zenodo, doi.org, Mendeley Data, ISRIC, HydroSHEDS, geoBoundaries, Leeds Research Data, Crossref and the DE Africa endpoints. |
| Accounts | No Google Earth Engine, DE Africa Sandbox, Planet or institutional (NIHSA/NiMet/NASRDA/NGSA/IITA/FMW) access. None is assumed. |
| Browser map in this sandbox | The Leaflet CDN and OSM tiles are not reachable from the container, so the map iframe renders empty here. It works on a normal network. |

## Stage 1 — what each source actually contains

| source | brief said | verified reality | usable for |
|---|---|---|---|
| **Soils4Africa** (Zenodo 17699297, v1, 2026-06-26, CC BY 4.0) | field obs + released lab data | The Zenodo record holds **field data only**: 13,876 sites, of which **1,549 in Nigeria**. All 1,549 fall inside the geoBoundaries polygon, across 36 of the 37 ADM1 units. Survey dates run 2022-09-08 → 2023-11-29. The file has **no sand/silt/clay columns**. Every download link on the AfricaSIS lab-data page is a placeholder (`href="#"`). The publisher says QC is ongoing. | Displaying measured field context (land use, slope class, depth restriction, erosion, surface crust). **Not** a texture target. |
| **Ozoro texture/moisture** (Mendeley ph9fx5bj9n v1, 2025, CC BY 4.0) | 750 samples, 0–10 cm | The only file is a **.docx manuscript**. Its texture table has **50 rows** (described as aggregated from 750 samples at 50 locations), and **no coordinates** anywhere. The method is a **jar sedimentation test**. Rows sum to 99–101 %. Mean sand/clay/silt is 75.9/11.8/12.3 %. | Area-level context for Ozoro only. **Cannot** be georeferenced, so it cannot train or validate a spatial model. |
| **Southern Nigeria wetlands** (Leeds 10.5518/1314, CC BY 4.0) | 10 m map (2018) + control points | The 71 kB archive **does not contain the map**: `Wetlandmap.tif` and `Wetlandmap.shp` are missing (only sidecars are present). The `.tfw` implies ~50 m pixels, not 10 m. **1,051 control points** in 8 classes. Of these, 18 are outside Nigeria (one at −62°), 16 have fewer than 3 decimals (≥110 m error; two have 1 decimal ≈ 11 km), and 1 is a duplicate, leaving **1,016 usable**. There are **no observation dates**, and the shapefile has no `.dbf` (attributes come from the xlsx). | Candidate labels for a wetland/water classifier, *if* date-matched imagery is ingested. No wall-to-wall wetland map exists. |
| **EO4Forest Lagos/Ogun** (Zenodo 10882149, CC BY 4.0) | land cover 2015/19/22/23, 20 m | Confirmed: 20 m maps in UTM 31N with classes water, urbanized, **soil (bare ground)**, cropland, grassland, forest. The sample files hold **155,902 training / 20,472 validation** points, against 112k / 11.9k stated in the record. **Leakage:** the median validation point is 212 m from the nearest training point, and 27 % are within 100 m. The published accuracies (OA 0.79, Soil F1 0.73 for 2023-12) are therefore optimistic, not independent. | Historical visible-surface context. Candidate labels, but only with re-split spatial blocks. |
| **Hadejia HAD-FCDR25** (Zenodo 15204588, CC BY 4.0) | 2020/2022 flood extents | Confirmed: 3 m per-scene and combined flood extents (PlanetScope + Sentinel-1), flood frequency (cropland only), permanent water and land cover. Coverage is **Hadejia LGA only (47.5 km²)**. Test points: 300 per year, labelled from **Sentinel-2 MNDWI maps**. That is a different sensor from the extents, but still EO-derived, not field truth. Only **5 survey responses** are released. | Displaying historical flood extents. Partial sensor-independent evaluation of flood maps. |
| **Geotechnical, Ibadan** (Mendeley cts2jkgvrw v2, CC BY 4.0) | CBR / strength / density | 9 pits and 41 sample rows, with Atterberg limits, grain size, OMC/MDD, cohesion/friction, consolidation and permeability. **No coordinates and no CBR.** No vehicle outcomes. | Engineering background only. Not mappable, not trainable. |
| **HydroBASINS v1c** | basins | Levels 6 and 8: IDs are unique and every `NEXT_DOWN` resolves within Africa. 147 (L6) and 1,387 (L8) basins intersect Nigeria. | Basin identity and topology. |
| **geoBoundaries NGA** | authoritative boundary | gbOpen ADM0/ADM1 from GRID3 (year represented 2022), CC BY 4.0. Valid geometry, 37 ADM1 units. | Nigeria filter (point-in-polygon, never a bbox). |
| **SoilGrids 2.0** (CC BY 4.0, confirmed on docs.isric.org) | covariate | Ingested. Sand/silt/clay × 6 depths × mean/Q05/Q50/Q95 (72 layers), on the native 250 m Homolosine grid over Nigeria. Retrieved by WCS: values are identical to the ISRIC VRTs where both have data, and nodata was restored from a VRT-extracted mask (mismatch counts are tagged in every file). int16 g/kg. | Modelled prior shown separately from measured texture. Never used as evidence or truth. |
| **DE Africa WOfS all-time** (CC BY 4.0, confirmed in the DE Africa spec) | water history | Ingested. All 131 tiles touching Nigeria, v1.0.0, 1984-01-01 → 2025-12-31, 30 m, EPSG:6933; all 393 files match the publisher's SHA-1. Of 3,000 random points in Nigeria, 10.2 % had ≥1 water detection, 7.2 % ≥2 and 5.2 % ≥5; 3.8 % had no clear observation. | National historical water frequency. Hazard flag at ≥2 detections (precautionary rule, `configs/assessment.yaml`). |
| **DE Africa GeoMAD Sentinel-2 annual** (CC BY 4.0) | imagery features | The 2018 composite (the wetland study's map year) is read remotely: 10 m, uint16 reflectance ×10⁴, plus EMAD/SMAD/BCMAD. | Features for the wetland classifier. |
| iSDAsoil, Sentinel-1 | covariates | **Not audited yet.** | — |
| NIHSA, NiMet, NASRDA, NGSA, IITA, FMW | candidates | No public machine-readable access verified. | Formal data requests needed. |

## Consequences for training (Stage 3 decision, made before any training)

| candidate model | decision | reason |
|---|---|---|
| Sand/silt/clay regression | **Do not train** | No measured, georeferenced Nigerian texture is available: S4A lab data can't be downloaded and Ozoro has no coordinates. Training on SoilGrids/iSDA outputs and calling it accuracy would be circular. |
| Visible-surface segmentation (image model) | **Do not train** | No Nigerian labelled *imagery* (image chips with masks) is available, only point labels on maps. |
| Wetland / water classifier | **Trained (Stage 3)** | See the Stage 3 section below and `docs/model_cards/wetland_rf_geomad2018.md`. |
| Flood extent classifier | **Do not train** | The publisher's maps already exist. Re-deriving them adds nothing, and testing against their MNDWI points is only sensor-independent. |
| Trafficability | **Disabled** | No paired soil/vehicle/outcome data and no expert validation exist. |

## Stage 3 — training actually performed (2026-11-27)

Only one model met the prerequisites: the **wetland / open-water classifier**. The full card is
`docs/model_cards/wetland_rf_geomad2018.md`.

| item | result |
|---|---|
| Data | 1,005 labelled points (of the 1,016 that passed QC), 2018 Sentinel-2 GeoMAD + WOfS features, 27 tiles |
| Split | 45 held-out 25 km blocks (207 points) with a 2 km leakage buffer; min train–test distance 2.2 km |
| Majority / rule baseline macro-F1 | 0.197 / 0.505 |
| Random Forest macro-F1 (held out) | **0.726** (95 % block-bootstrap CI 0.61–0.82) |
| Improvement over rule | +0.22 (CI +0.10 to +0.31) |
| Weak class | vegetated wetland F1 0.505 (CI 0.21–0.72); half of true wetlands predicted as "other" |
| Gate (pre-registered) | passed on the point estimate. The CI lower bound sits at the margin, so the pass is not robust |
| Deployment | opt-in research layer (`include_models=true`), labelled modelled, never drives hazard flags, refused outside the training domain |
| Independence | spatially held out, but the same labelling campaign, so **not** an external validation |

**Not trained (unchanged):**
- soil texture: no measured, georeferenced Nigerian labels;
- image segmentation: no labelled Nigerian imagery;
- trafficability: no outcome data.

## Problems found during the work, and fixes

| problem | fix |
|---|---|
| SoilGrids VRT extraction through the proxy slowed to ~3 min/layer in parallel | Switched to ISRIC WCS (~40 s/layer); values verified identical to the VRT |
| WCS encodes nodata as 0 with no tag | Nodata restored from a VRT-extracted mask. Zeros outside the mask were checked against the VRT (5/5 sampled are genuine 0 g/kg) and kept as data; every file is tagged with the counts |
| SoilGrids has no values in urban cores (Abuja, Lagos Island) | Reported as nodata, never filled; tested; documented in the limitations |
| GeoMAD feature extraction stalled silently (no HTTP timeout) | GDAL HTTP timeouts, per-tile checkpoints and progress logging added |
| pandas 3 returns Arrow string arrays that scikit-learn cannot index | Explicit `to_numpy` conversion |
| Dashboard marker invisible (Leaflet icon path broken in the iframe) | Vector marker; map rendering verified in Chromium |

## What remains unknown

- Whether and when the Soils4Africa lab texture will be released, and with which methods and depths.
- The licence text inside the HydroBASINS package (the tech doc PDF is extracted but not yet reviewed).
- Real-world (external) accuracy of the wetland model. It needs independently collected, dated wetland observations.
- Whether the iSDAsoil 30 m and Sentinel-1 radar layers would improve the wetland model, especially for vegetated wetland under cloud.
- Whether the Leeds wetland map can be obtained from the authors (it is not in the deposit).
- The Ozoro sampling coordinates (only the authors have them).
