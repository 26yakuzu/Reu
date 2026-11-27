# Model cards

**No models have been trained.** Each candidate's decision and blocker is in `docs/research/GAP_REPORT.md`,
and `GET /models` returns the same list.

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
