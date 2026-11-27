"""Paths and registry loading."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("TERRASENSE_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
MANIFEST_DIR = ARTIFACTS_DIR / "manifests"
REGISTRY_PATH = REPO_ROOT / "configs" / "sources.yaml"


@lru_cache(maxsize=1)
def load_registry(path: Path = REGISTRY_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def source_by_id(source_id: str) -> dict:
    reg = load_registry()
    if reg["boundary"]["id"] == source_id:
        return reg["boundary"]
    for s in reg["sources"]:
        if s["id"] == source_id:
            return s
    raise KeyError(source_id)
