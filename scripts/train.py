"""Training entry point. Refuses to train models whose prerequisites are not met.

Each candidate lists the evidence it needs; nothing is trained until that evidence exists.
"""
import sys

BLOCKERS = {
    "soil_texture": "No measured, georeferenced Nigerian sand/silt/clay (S4A lab not downloadable; Ozoro has no coordinates).",
    "surface_segmentation": "No Nigerian labelled imagery (chips + masks) with independent test sites.",
    "wetland_classifier": "Control points exist (1,016 after QC) but date-matched Sentinel-1/2 features are not ingested yet.",
    "trafficability": "Disabled: no paired soil/vehicle/outcome data or expert validation.",
}
for k, v in BLOCKERS.items():
    print(f"[blocked] {k}: {v}")
print("\nNo model trained. See docs/research/GAP_REPORT.md.")
sys.exit(2)
