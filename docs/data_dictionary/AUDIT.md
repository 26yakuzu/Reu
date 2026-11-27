# Dataset audit (generated)

Generated `2026-11-27T09:16:23+00:00` by `python -I scripts/audit.py`. Boundary: `geoBoundaries-NGA-ADM0.geojson`.
Every value below was computed from files in `data/raw/`; none is copied from the project brief.

## `geoboundaries_nga`

| field | value |
|---|---|
| status | `ok` |
| crs | `EPSG:4326` |
| adm0_valid | `True` |
| bounds | `[2.6926, 4.2702, 14.678, 13.8857]` |
| area_km2 | `912722` |
| adm1_units | `37` |
| adm1_names | `["Abia", "Abuja Federal Capital Territory", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"]` |

## `s4a_field`

| field | value |
|---|---|
| status | `ok` |
| rows_total | `13876` |
| columns | `55` |
| nigeria_rows | `1549` |
| unique_plot_codes | `1549` |
| points | `{"n": 1549, "invalid_coordinates": 0, "inside_nigeria": 1549, "outside_nigeria_valid": 0, "bbox_valid_inside": [2.9145957, 4.6626338, 12.8754129, 13.5056362]}` |
| X_Y_equal_lon_lat | `True` |
| coordinate_decimals | `{"3": 2, "4": 6, "5": 51, "6": 152, "7": 1338}` |
| survey_date_range | `["2022-09-08", "2023-11-29"]` |
| unparseable_dates | `0` |
| texture_columns_present | `[]` |
| categorical_counts | `{"main_land_use": {"Cultivated and managed land (terrestial area)": 1261, "Semi-natural vegetation": 216, "Cultivated aquatic or regularly flooded areas": 72}, "bare_soil": {"No": 1466, "Yes": 83}, "lndform": {"Level land (Gradient < 10%, relief intensity < 50 m/km)": 1158, "Sloping land (Gradient 10\u201330%, relief intensity 50-150 m/km)": 372, "Steep land (Gradient > 30%, relief intensity > 150 …` |
| sites_per_state | `{"Bauchi": 151, "Niger": 114, "Taraba": 89, "Kano": 83, "Kaduna": 80, "Jigawa": 72, "Gombe": 72, "Kebbi": 72, "Nasarawa": 66, "Yobe": 66, "Benue": 65, "Oyo": 63, "Kwara": 57, "Plateau": 57, "Kogi": 56, "Sokoto": 55, "Katsina": 46, "Adamawa": 44, "Ogun": 34, "Cross River": 24, "Borno": 24, "Edo": 20, "Abuja Federal Capital Territory": 20, "Enugu": 15, "Ebonyi": 12, "Akwa Ibom": 12, "Rivers": 12, "O …` |

**Eligibility by role**

- **soil_texture_target**: NO — field file has no sand/silt/clay; lab release not downloadable
- **surface_context_display**: YES — measured field description at plot, survey date shown
- **visible_surface_labels**: LIMITED — bare_soil is Yes/No at plot level only (agricultural sites)

## `ozoro_texture`

| field | value |
|---|---|
| status | `ok` |
| file_type | `docx (manuscript)` |
| tables | `[[52, 9], [53, 5], [53, 2]]` |
| texture_table | `{"header": ["Exp.No.", "SandyMl", "ClayMl", "SiltMl", "TotalSoil", "%Sandy", "%Clay", "%Silt", "Soil Type"], "data_rows": 50, "sum_pct_min": 99.0, "sum_pct_max": 101.0, "rows_not_summing_to_100": 0, "mean_sand_clay_silt_pct": [75.9, 11.8, 12.3], "classes": {"Sandy loam": 20, "Loamy sand": 13, "Sand": 10, "Sandy clay loam": 4, "Sandy clay": 2, "Sandy Clay loam": 1}}` |
| coordinate_mentions | `[]` |

**Eligibility by role**

- **soil_texture_target**: NO — 50 aggregated 'experiment' rows (not 750 samples), no coordinates, jar-test method; cannot be georeferenced
- **context_display**: YES — area-level summary for Ozoro (Isoko North LGA), cite as such

## `wetland_south_ng`

| field | value |
|---|---|
| status | `ok` |
| files_present | `["GroundControlPoint.cpg", "GroundControlPoint.prj", "GroundControlPoint.sbn", "GroundControlPoint.sbx", "GroundControlPoint.shp", "GroundControlPoint.shp.xml", "GroundControlPoint.shx", "Ground_control_points_1.xlsx", "Wetlandmap.cpg", "Wetlandmap.dbf", "Wetlandmap.prj", "Wetlandmap.sbn", "Wetlandmap.sbx", "Wetlandmap.shp.xml", "Wetlandmap.shx", "Wetlandmap.tfw", "Wetlandmap.tif.aux.xml", "Wetlan …` |
| wetland_map_raster_present | `False` |
| wetland_map_vector_geometry_present | `False` |
| gcp_shapefile_attributes_present | `False` |
| wetlandmap_tfw_pixel_deg | `0.0004491576` |
| wetlandmap_tfw_pixel_m_approx | `50.0` |
| gcp_rows | `1051` |
| gcp_classes | `{"Forest": 206, "Built up/bare land": 151, "Mangrove": 141, "Deep water": 135, "Swamp": 130, "Cultivated land": 124, "Shallow water": 95, "Marsh": 69}` |
| gcp_points | `{"n": 1051, "invalid_coordinates": 0, "inside_nigeria": 1033, "outside_nigeria_valid": 18, "bbox_valid_inside": [2.71, 4.2996, 9.3202, 7.4286]}` |
| gcp_coordinate_decimals | `{"1": 2, "2": 14, "3": 79, "4": 956}` |
| gcp_low_precision_lt3_decimals | `16` |
| gcp_duplicate_coordinates | `1` |
| gcp_observation_date | `not recorded in file` |

**Eligibility by role**

- **wetland_map_display**: NO — map raster/vector geometry absent from the archive
- **wetland_classifier_labels**: CANDIDATE — ~1k labelled points, 8 classes; no dates; need date-matched imagery (DE Africa S2/S1) and spatial-block splits; drop invalid/low-precision points

## `eo4forest_lagos_ogun`

| field | value |
|---|---|
| status | `ok` |
| crs_samples | `EPSG:32631` |
| training_points | `155902` |
| validation_points | `20472` |
| stated_in_record | `{"training": 112000, "validation": 11900}` |
| training_class_counts | `{"tree cover": 67123, "urbanized": 23287, "grassland": 19051, "cropland": 15858, "water": 15409, "soil": 15127}` |
| validation_class_counts | `{"tree cover": 5744, "urbanized": 4330, "soil": 3073, "grassland": 2994, "water": 2139, "cropland": 2131, "5": 1}` |
| validation_points_geo | `{"n": 20472, "invalid_coordinates": 0, "inside_nigeria": 20350, "outside_nigeria_valid": 122, "bbox_valid_inside": [2.7026351946089635, 6.304132024731915, 4.605037393158019, 7.949127637977328]}` |
| val_to_nearest_train_m | `{"p05": 23.9, "median": 212.4, "p95": 806.6, "share_lt_100m": 0.274, "exact_coordinate_overlap": 0}` |
| legend | `["0 25 227 35 0 No data", "1 117 168 255 255 Water", "2 254 95 103 255 Urbanized", "3 150 134 112 255 Soil", "4 255 228 126 255 Cropland", "5 68 225 144 255 Grasland", "6 46 149 68 255 Forest"]` |
| published_accuracy / Accuracy_2015-12_.txt | `{"overall_accuracy": 0.7004, "f1_class3_soil": 0.5725}` |
| published_accuracy / Accuracy_2019-01_.txt | `{"overall_accuracy": 0.7627, "f1_class3_soil": 0.6369}` |
| published_accuracy / Accuracy_2022-12.txt | `{"overall_accuracy": 0.8598, "f1_class3_soil": 0.8528}` |
| published_accuracy / Accuracy_2022_01.txt | `{"overall_accuracy": null, "f1_class3_soil": null}` |
| published_accuracy / Accuracy_2023-12.txt | `{"overall_accuracy": 0.7944, "f1_class3_soil": 0.7282}` |
| maps_extracted / AOI0_2023-12.tif | `{"crs": "EPSG:32631", "res": [20.0, 20.0], "shape": [9106, 10580], "dtype": "float64", "nodata": null}` |

**Eligibility by role**

- **land_cover_display**: YES — published map, 20 m, label as 'EO4Forest RF classification (year)'
- **visible_surface_labels**: CANDIDATE — photo-interpreted classes; 'Soil' = bare ground, NOT sand
- **independent_accuracy**: NO — published validation points sit close to training points (see val_to_nearest_train_m); scores are optimistic, not independent

## `hadejia_flood`

| field | value |
|---|---|
| status | `ok` |
| study_area | `{"crs": "EPSG:32632", "area_km2": 47.54, "adm2": ["Hadejia"], "adm1": ["Jigawa"], "centroid_inside_nigeria": true}` |
| rasters / Flood_Extent_Layers_RF_S1_and_PS/2020/Combined_Flood_Extent_PS_S1_2020.tif | `{"crs": "EPSG:32632", "res_m": [3.0, 3.0], "shape": [2847, 2835], "dtype": "float32", "nodata": 0.0}` |
| rasters / Flood_Extent_Layers_RF_S1_and_PS/2022/Combined_Flood_Extent_PS_S1_2022.tif | `{"crs": "EPSG:32632", "res_m": [3.0, 3.0], "shape": [2895, 2848], "dtype": "float32", "nodata": 0.0}` |
| rasters / Flood_Frequency_Layers/Flood_Frequency_PS_S1_Combine_2020_Mask_Cropland.tif | `{"crs": "EPSG:32632", "res_m": [3.0, 3.0], "shape": [2815, 2834], "dtype": "float32", "nodata": -9999.0}` |
| rasters / Flood_Frequency_Layers/Flood_Frequency_PS_S1_Combine_2022_Mask_Cropland.tif | `{"crs": "EPSG:32632", "res_m": [3.0, 3.0], "shape": [2877, 2846], "dtype": "float32", "nodata": -9999.0}` |
| rasters / Perm_Water_Layer/Permanenet_Water_2022.tif | `{"crs": "EPSG:32632", "res_m": [3.0, 3.0], "shape": [1860, 2732], "dtype": "float32", "nodata": -9999.0}` |
| rasters / Land_Cover_Layers/Land_Cover_Layer_2022.tif | `{"crs": "EPSG:32632", "res_m": [3.0, 3.0], "shape": [2895, 2848], "dtype": "float32", "nodata": 0.0}` |
| per_date_flood_layers | `["PS_20200925_flood_layer.tif", "PS_20201004_flood_layer.tif", "PS_20201012_flood_layer.tif", "PS_20201028_flood_layer.tif", "PS_20220807_flood_layer.tif", "PS_20220920_flood_layer.tif", "PS_20220926_flood_layer.tif", "PS_20220928_flood_layer.tif", "PS_20221001_flood_layer.tif", "PS_20221008_flood_layer.tif", "PS_20221018_flood_layer.tif", "PS_20221028_flood_layer.tif", "S1_20200814_flood_layer.ti …` |
| testing_points / Flood_2020_Random_Testing_Points.shp | `{"n": 300, "label_field": "MNDWI_Valu", "counts": {"1": 158, "0": 142}}` |
| testing_points / Flood_2022_Random_Testing_Points.shp | `{"n": 300, "label_field": "MNDWI_Valu", "counts": {"1": 187, "0": 113}}` |
| survey_rows_released | `5` |
| survey_note | `Th survey/participatory mapping data contains just a few samples because it is been used for another research work. The full survey data may be made available upon request from the corresponding author.` |

**Eligibility by role**

- **flood_extent_history_display**: YES — 2020/2022 event extents, dated per scene, 3 m, Hadejia LGA only (~48 km2)
- **independent_flood_evaluation**: PARTIAL — 300 test points/year labelled from Sentinel-2 MNDWI maps (a different sensor than the S1/PlanetScope extents) — sensor-independent but still EO-derived, not field truth
- **participatory_truth**: NO — only 5 survey responses released

## `geotech_ibadan`

| field | value |
|---|---|
| status | `ok` |
| sheets | `["undisturbed"]` |
| rows | `41` |
| pits | `["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9"]` |
| columns | `["Sample Locations", "NMC (%)", "Gs", "LL", "PL", "PI", "LI", "FL", "TI", "G", "CS", "MS", "FS", "F", "OMC%", "MDD (kN/m3)", "Consistency limit", "Grain size", "Cohesion (kPa)", "Angle of Friction (\u00b0)", "Coefficient of Compressibilty Mp ", "Preconsolidation Pressure", "Compression Index", "Swelling Index", "Recompression Index", "Coefficient of Compressibilty ", "Settlement ", "Permeability", …` |
| coordinates_present | `False` |
| cbr_present | `False` |

**Eligibility by role**

- **model_training**: NO — 9 pits, no coordinates, no outcomes
- **context_display**: LIMITED — Ibadan-area engineering ranges only, cannot be mapped to a point

## `hydrobasins_af`

| field | value |
|---|---|
| lev06 | `{"status": "ok", "crs": "EPSG:4326", "africa_basins": 3597, "basins_intersecting_nigeria": 147, "fields": ["HYBAS_ID", "NEXT_DOWN", "NEXT_SINK", "MAIN_BAS", "DIST_SINK", "DIST_MAIN", "SUB_AREA", "UP_AREA", "PFAF_ID", "ENDO", "COAST", "ORDER", "SORT"], "hybas_id_unique": true, "next_down_resolves": true}` |
| lev08 | `{"status": "ok", "crs": "EPSG:4326", "africa_basins": 41372, "basins_intersecting_nigeria": 1387, "fields": ["HYBAS_ID", "NEXT_DOWN", "NEXT_SINK", "MAIN_BAS", "DIST_SINK", "DIST_MAIN", "SUB_AREA", "UP_AREA", "PFAF_ID", "ENDO", "COAST", "ORDER", "SORT"], "hybas_id_unique": true, "next_down_resolves": true}` |

**Eligibility by role**

- **basin_identity**: YES — verified IDs + topology (NEXT_DOWN); drainage units, NOT wetlands

## Registered but not audited

- `s4a_lab`: blocked
- `soilgrids`: not_audited
- `isdasoil`: not_yet_audited
- `deafrica_wofs`: not_yet_audited
- `cat_rellis`: not_audited
- `ng_agencies`: no_access
