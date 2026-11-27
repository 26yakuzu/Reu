# Data dictionary

`AUDIT.md` (generated) holds the measured facts per raw source. This page describes the **processed**
files in `data/processed/<version>/`.

| file | CRS | resolution | values / fields | source |
|---|---|---|---|---|
| `eo4forest_landcover_2023-12.tif` | EPSG:32631 | 20 m | uint8: 0 nodata, 1 water, 2 urbanized, 3 soil (bare ground), 4 cropland, 5 grassland, 6 forest | eo4forest_lagos_ogun |
| `hadejia_landcover_2022.tif` | EPSG:32632 | 3 m | uint8: 0 nodata, 1 bare soil, 2 built-up, 3 cultivated, 4 fallow, 5 tree, 6 water (from publisher QML) | hadejia_flood |
| `hadejia_flood_extent_{2020,2022}.tif` | EPSG:32632 | 3 m | uint8: 1 flooded in ≥1 scene; 0 not flooded *or* no data (source conflates them) | hadejia_flood |
| `hadejia_flood_freq_{2020,2022}.tif` | EPSG:32632 | 3 m | uint8: number of scenes flagged flooded (of 11 in 2020, 12 in 2022); 255 nodata (non-cropland). Source stored fraction k/N as float32; converted exactly | hadejia_flood |
| `hadejia_perm_water_2022.tif` | EPSG:32632 | 3 m | uint8: 1 permanent water; 0 nodata | hadejia_flood |
| `s4a_field_nga.parquet` | EPSG:4326 | point | all 55 Soils4Africa field columns; `survey_date` as date; `qc_reject_reason` | s4a_field |
| `wetland_gcp_south_ng.parquet` | EPSG:4326 | point | `class_code`, `class_name`, `lon`, `lat`, `coord_decimals`, `qc_reject_reason` (outside_nigeria / coordinate_precision_lt_3_decimals / duplicate_coordinate) | wetland_south_ng |
| `hybas_lev{06,08}_nga.parquet` | EPSG:4326 | polygon | HydroBASINS fields (HYBAS_ID, NEXT_DOWN, PFAF_ID, SUB_AREA km², UP_AREA km², ENDO, COAST, ORDER, …). Polygons intersecting Nigeria, **not clipped** | hydrobasins_af |
| `hybas_lev{06,08}_af_topology.parquet` | — | table | Africa-wide attribute table for upstream/downstream traversal | hydrobasins_af |
| `nga_adm{0,1}_display.geojson` | EPSG:4326 | polygon | simplified for display only; analysis uses the raw polygon | geoboundaries_nga |
| `coverage_outlines.geojson` | EPSG:4326 | polygon | EO4Forest AOI, Hadejia study area | eo4forest / hadejia |

| `wofs_maxfreq_display.tif` | EPSG:6933 | 480 m | uint8: max WOfS frequency (%) within 16×16 30 m pixels; 255 nodata. **Display only** | deafrica_wofs |

## Raw layers read directly (already in native, compressed, checksummed form)

| path | CRS | resolution | values | source |
|---|---|---|---|---|
| `data/raw/deafrica_wofs/x###y###/*_count_wet.tif`, `*_count_clear.tif` | EPSG:6933 | 30 m | int16 counts of wet / clear Landsat observations 1984–2025; nodata −999. Frequency = wet / clear (DE Africa definition); clear = 0 → nodata | deafrica_wofs (131 tiles, publisher sha1 verified) |
| `data/raw/soilgrids/{sand,silt,clay}_{depth}_{mean,Q0.05,Q0.5,Q0.95}.tif` | Interrupted Goode Homolosine | 250 m | int16 g/kg (÷10 → %); nodata −32768. Depths 0–5, 5–15, 15–30, 30–60, 60–100, 100–200 cm. **Modelled** | soilgrids |
| `data/processed/features/wetland_gcp_features_geomad2018.parquet` | — | point (3×3 px median at 10 m) | GeoMAD 2018 bands B02–B12 (reflectance ×10⁴), EMAD/SMAD/BCMAD, COUNT, NDVI/MNDWI/NDWI/NDMI, WOfS freq/clear, plus labels | wetland_south_ng + DE Africa gm_s2_annual |

Units: areas in km², distances in metres, computed in the local UTM zone (31N–33N).
SoilGrids units, when ingested, are g/kg; divide by 10 for %.
