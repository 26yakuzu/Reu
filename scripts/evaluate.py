"""Print held-out evaluation for trained models (from artifacts/reports). Usage: python -I scripts/evaluate.py"""
import json
import sys

from terrasense.config import ARTIFACTS_DIR

p = ARTIFACTS_DIR / "reports" / "wetland_rf_results.json"
if not p.exists():
    print("No trained models. Run: python -I scripts/train.py --model wetland")
    sys.exit(2)
r = json.loads(p.read_text())
for name in ("baseline_majority", "baseline_rule_wofs_mndwi", "random_forest_test"):
    m = r[name]
    print(f"\n== {name}  n={m['n']}  accuracy={m['accuracy']}  macro-F1={m['macro_f1']}")
    for c, d in m["per_class"].items():
        print(f"   {c:18s} P={d['precision']:.3f} R={d['recall']:.3f} F1={d['f1-score']:.3f} IoU={m['iou'][c]:.3f} support={int(d['support'])}")
    print("   confusion (rows=true, cols=pred, order=%s):" % m["confusion_matrix"]["labels"])
    for row in m["confusion_matrix"]["rows_true_cols_pred"]:
        print("     ", row)
print("\nby state:", r["random_forest_test_by_state"])
print("block-bootstrap 95% CI:", r.get("block_bootstrap_95ci"))
print("deployment gate:", r["deployment_gate"])
print("NOTE: test points are spatially held out but come from the same labelling campaign; not externally independent.")
