"""Fetch DE Africa WOfS all-time summary tiles over Nigeria (~131 tiles, ~2 MB each, sha1-verified).

Usage: python -I scripts/fetch_wofs.py [--workers 6]
"""
import argparse
from collections import Counter

from terrasense.ingest.wofs import fetch_wofs

p = argparse.ArgumentParser()
p.add_argument("--workers", type=int, default=6)
recs = fetch_wofs(p.parse_args().workers)
print(Counter(r.status for r in recs))
print("checksum failures:", [r.key for r in recs if r.checksum_ok is False])
