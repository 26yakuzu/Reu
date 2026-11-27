"""Extract SoilGrids 250 m windows over Nigeria (native grid, no resampling).

Usage: python -I scripts/fetch_soilgrids.py [--depths 0-5cm 5-15cm] [--stats Q0.5] [--workers 6]
Default method: WCS server-side subset (~40 s/layer), nodata restored from a VRT-extracted mask.
--method vrt reads ISRIC VRTs directly (slow through proxies, ~3 min/layer).
"""
import argparse

from terrasense.ingest.soilgrids import DEPTHS, PROPS, STATS, fetch_soilgrids, fetch_soilgrids_wcs

p = argparse.ArgumentParser()
p.add_argument("--props", nargs="*", default=list(PROPS))
p.add_argument("--depths", nargs="*", default=list(DEPTHS))
p.add_argument("--stats", nargs="*", default=list(STATS))
p.add_argument("--workers", type=int, default=3)
p.add_argument("--method", choices=["wcs", "vrt"], default="wcs")
a = p.parse_args()
fn = fetch_soilgrids_wcs if a.method == "wcs" else fetch_soilgrids
recs = fn(a.props, a.depths, a.stats, a.workers)
bad = [r for r in recs if r.status.startswith("error")]
print(f"done: {len(recs) - len(bad)} ok, {len(bad)} errors")
