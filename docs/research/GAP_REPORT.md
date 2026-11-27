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
| SoilGrids 250 m | covariate | Server reachable. **Not yet ingested.** | Planned modelled prior (units g/kg; Q05/Q50/Q95). |
| iSDAsoil, DE Africa WOfS / S1 / S2 | covariates | **Not audited yet.** | — |
| NIHSA, NiMet, NASRDA, NGSA, IITA, FMW | candidates | No public machine-readable access verified. | Formal data requests needed. |

## Consequences for training (Stage 3 decision, made before any training)

| candidate model | decision | reason |
|---|---|---|
| Sand/silt/clay regression | **Do not train** | No measured, georeferenced Nigerian texture is available: S4A lab data can't be downloaded and Ozoro has no coordinates. Training on SoilGrids/iSDA outputs and calling it accuracy would be circular. |
| Visible-surface segmentation (image model) | **Do not train** | No Nigerian labelled *imagery* (image chips with masks) is available, only point labels on maps. |
| Wetland / water classifier | **Possible next step** | 1,016 cleaned control points could work once date-matched Sentinel-2/1 features are ingested from DE Africa. That needs spatial-block splits (`terrasense.models.splits`), a baseline (majority class, plus an MNDWI threshold), then a Random Forest. The undated labels are a known weakness. |
| Flood extent classifier | **Do not train** | The publisher's maps already exist. Re-deriving them adds nothing, and testing against their MNDWI points is only sensor-independent. |
| Trafficability | **Disabled** | No paired soil/vehicle/outcome data and no expert validation exist. |

## What remains unknown

- Whether and when the Soils4Africa lab texture will be released, and with which methods and depths.
- The licence text inside the HydroBASINS package (the tech doc PDF is extracted but not yet reviewed).
- The DE Africa product paths, dates and cloud masks over the wetland control points and the Lagos/Ogun pilot.
- Whether the Leeds wetland map can be obtained from the authors (it is not in the deposit).
- The Ozoro sampling coordinates (only the authors have them).
