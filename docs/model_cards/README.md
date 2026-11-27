# Model cards

| model | status | card |
|---|---|---|
| `wetland_rf_geomad2018` | trained; held-out macro-F1 0.73 (CI 0.61–0.82); opt-in research layer | [wetland_rf_geomad2018.md](wetland_rf_geomad2018.md) |
| soil texture regressor | **not trained**: no measured, georeferenced Nigerian labels | — |
| surface segmentation | **not trained**: no labelled Nigerian imagery | — |
| trafficability | **disabled**: no outcome data | — |

`GET /models` returns the same information.

When a model is trained, add a card here (`<model_id>.md`) with:
- intended use and out-of-scope uses;
- training data (source IDs and versions from `configs/sources.yaml`, sample counts, geographic coverage);
- label mapping;
- split method (spatial block size, seed, plus the leakage report from `terrasense.models.splits`);
- the baseline used;
- hyper-parameter search space and seed;
- metrics on the untouched test set:
  - classification: per-class P/R/F1, IoU, confusion matrix;
  - regression: MAE/RMSE/bias and interval coverage;
- performance by region and season;
- known failure modes;
- the artifact sha256.
