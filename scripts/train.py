"""Training entry point.

  python -I scripts/train.py --model wetland      # features (cached) -> baselines -> RF -> held-out test
  python -I scripts/train.py                      # list models and blockers

Models whose prerequisites are not met refuse to train.
"""
import argparse
import json
import sys

BLOCKED = {
    "soil_texture": "No measured, georeferenced Nigerian sand/silt/clay (S4A lab not downloadable; Ozoro has no coordinates).",
    "surface_segmentation": "No Nigerian labelled imagery (chips + masks) with independent test sites.",
    "trafficability": "Disabled: no paired soil/vehicle/outcome data or expert validation.",
}
p = argparse.ArgumentParser()
p.add_argument("--model", choices=["wetland", *BLOCKED])
p.add_argument("--rebuild-features", action="store_true")
a = p.parse_args()
if a.model is None or a.model in BLOCKED:
    for k, v in BLOCKED.items():
        print(f"[blocked] {k}: {v}")
    print("[available] wetland: python -I scripts/train.py --model wetland")
    sys.exit(2 if a.model else 0)

from terrasense.models.wetland import build_features, train_and_evaluate  # noqa: E402

fp = build_features(force=a.rebuild_features)
r = train_and_evaluate(fp)
show = {k: r[k] for k in ("n_total_complete", "dropped_incomplete_features", "split", "class_counts", "rf_search", "deployment_gate")}
show["test_macro_f1"] = {k: r[k]["macro_f1"] for k in ("baseline_majority", "baseline_rule_wofs_mndwi", "random_forest_test")}
print(json.dumps(show, indent=2, default=str))
print("full results: artifacts/reports/wetland_rf_results.json")
