"""Extract fetched archives (idempotent). Usage: python -I scripts/extract.py"""
from terrasense.ingest.extract import extract_all

for k, v in extract_all().items():
    print(f"{k:60s} {v}")
