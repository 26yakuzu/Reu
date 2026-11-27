"""Fetch registry sources into data/raw and record a checksum manifest.

Usage:
  python -I scripts/fetch.py                 # default (small) files
  python -I scripts/fetch.py --include-large # also large rasters / archives
  python -I scripts/fetch.py --only hadejia_flood --include-large
"""
import argparse

from terrasense.ingest.fetch import fetch_all, write_manifest

p = argparse.ArgumentParser()
p.add_argument("--include-large", action="store_true")
p.add_argument("--only", nargs="*")
a = p.parse_args()
recs = fetch_all(a.include_large, set(a.only) if a.only else None)
for r in recs:
    print(f"{r.status:28s} ok={str(r.checksum_ok):5s} {r.size or 0:>11,d}  {r.source_id}/{r.key}")
print("manifest:", write_manifest(recs))
