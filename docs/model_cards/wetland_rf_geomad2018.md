# Model card — `wetland_rf_geomad2018`

**Status:** research model. Served only on request (`include_models=true` / dashboard checkbox),
labelled as modelled. **Never** drives the observed-hazard state.
Source of all numbers: `artifacts/reports/wetland_rf_results.json`. Reproduce with
`python -I scripts/train.py --model wetland`.

## Intended use

- Indicates whether a location in **southern Nigeria** looked like open water, vegetated wetland
  (mangrove/swamp/marsh) or other land **in 2018**.
- Context for agricultural and construction screening, alongside observed layers.

**Out of scope:**
- current or seasonal conditions;
- flood forecasting;
- anything outside the training domain (convex hull of the training labels + 10 km; queries outside it
  return `outside_coverage`);
- any vehicle, crossing or engineering decision;
- treating class probabilities as risk (they are uncalibrated and not shown).

## Data

| item | value |
|---|---|
| Labels | Garba et al. (2023) ground control points, doi:10.5518/1314, CC BY 4.0. 1,051 points → 1,016 after QC (18 outside Nigeria, 16 with <3 coordinate decimals, 1 duplicate) → 1,005 with complete features (11 had no clear WOfS observation). **Undated**; the study map year is 2018. |
| Label mapping | Deep/Shallow water → `open_water`; Mangrove/Swamp/Marsh → `vegetated_wetland`; Forest/Cultivated land/Built up-bare land → `other` |
| Features (18) | DE Africa Sentinel-2 annual GeoMAD **2018**: B02–B12 (10 bands), EMAD, SMAD, BCMAD; NDVI, MNDWI, NDWI, NDMI; DE Africa WOfS all-time frequency (1984–2025). Each is a 3×3-pixel median at 10 m, to absorb the ~11 m coordinate precision. COUNT is excluded. |
| Features file | `data/processed/features/wetland_gcp_features_geomad2018.parquet`, sha256 `ded7d4eb…` |
| Coverage | 27 GeoMAD tiles; 14 states in the test set (Delta, Edo, Anambra, Bayelsa, Imo, Rivers, …) |

## Training protocol

- **Split:**
  - 25 km spatial blocks (EPSG:6933, 218 blocks); 45 whole blocks form the untouched test set (207 points).
  - Training points within **2 km** of any test point are dropped (2 removed).
  - The minimum train–test distance is then 2.23 km (median 11.8 km), with no duplicates.
- **Class counts:**
  - train: other 373, vegetated wetland 287, open water 136;
  - test: other 87, open water 75, vegetated wetland 45.
- **Baselines:**
  - majority class;
  - a transparent rule: open water if WOfS frequency ≥ 0.5 or MNDWI > 0, else other.
- **Model:**
  - `RandomForestClassifier(n_estimators=400, class_weight="balanced", random_state=20261127)`.
  - Grid over max_depth {None, 12} × min_samples_leaf {1, 3, 8} × max_features {sqrt, 0.5}.
  - The grid is searched with GroupKFold(5) over training blocks only.
  - Best: max_depth=None, max_features=0.5, min_samples_leaf=1. CV macro-F1 0.803 ± 0.047.
- **Deployment gate (set before results were seen):** held-out macro-F1 ≥ best baseline + 0.10 and ≥ 0.60.

## Results on the held-out test set (n = 207, 45 blocks)

| | accuracy | macro-F1 | F1 open water | F1 veg. wetland | F1 other |
|---|---|---|---|---|---|
| Majority baseline | 0.420 | 0.197 | 0.000 | 0.000 | 0.592 |
| Rule baseline (WOfS/MNDWI) | 0.662 | 0.505 | 0.803 | 0.000 | 0.711 |
| **Random Forest** | **0.759** | **0.726** | **0.874** | **0.505** | **0.798** |

RF per-class precision / recall / IoU:
- open water: 0.983 / 0.787 / 0.776;
- vegetated wetland: 0.500 / 0.511 / 0.338;
- other: 0.743 / 0.862 / 0.664.

RF confusion matrix (rows = true, columns = predicted; order open water, vegetated wetland, other):

```
open_water         [59, 12,  4]
vegetated_wetland  [ 0, 23, 22]
other              [ 1, 11, 75]
```

**Block-bootstrap 95 % confidence intervals** (2,000 resamples of test blocks):
- RF macro-F1: 0.61–0.82;
- rule baseline: 0.44–0.59;
- RF minus rule: **+0.10 to +0.31**;
- RF vegetated-wetland F1: **0.21–0.72**.

**Gate:** passed on the point estimate (0.726 vs 0.505 + 0.10). The lower CI bound of the improvement
(0.098) sits right at the margin, so the pass is **not robust**. What is robust is that the RF beats the
rule: the improvement CI excludes 0.

Most important features: B11 (SWIR1) 0.19, MNDWI 0.11, B08 (NIR) 0.10, B06 0.10, WOfS frequency 0.09.

Accuracy by state is reported in the results file, but each state has only 2–49 test points and is not
reliable.

## Known limitations and failure modes

- **Vegetated wetland is the weak class.** Half of the true wetlands are predicted as "other", and
  wetlands are confused with flooded forest and cultivated land. Its F1 interval is very wide.
- **Not externally independent.** The test points come from the same labelling campaign (same
  interpreters, protocol and likely the same imagery), so real-world accuracy is probably lower.
- **Undated labels** are matched to 2018 imagery. Seasonal wetlands may be dry in an annual geomedian.
- **CV vs held-out gap** (0.80 vs 0.73) suggests spatial heterogeneity between blocks.
- The training domain covers the southern states only. Northern wetlands (e.g. Hadejia–Nguru) are
  outside it and are refused.
- Inference reads GeoMAD tiles over the network (about 15 s); offline it returns `unavailable`.

## Artifact

`artifacts/models/wetland_rf_geomad2018.joblib` is not committed (gitignored). Running `train.py` again
regenerates it from the seeded protocol. sha256 of the build that produced the results above: `4b8aa2dc…80b3`.
