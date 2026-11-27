"""Build data/processed/<version>/ from data/raw. Usage: python -I scripts/prepare.py [--skip-rasters]"""
import argparse

from terrasense.ingest.prepare import prepare_all

p = argparse.ArgumentParser()
p.add_argument("--skip-rasters", action="store_true")
print("manifest:", prepare_all(p.parse_args().skip_rasters))
