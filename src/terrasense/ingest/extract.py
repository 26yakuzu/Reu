"""Safe extraction of raw archives into data/raw/<source>/extracted/.

Archives stay untouched. Members with absolute paths or '..' are refused.
`members` limits extraction (e.g. one year of the 0.8 GB-per-year land-cover maps).
"""
from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath

from terrasense.config import RAW_DIR

PLAN: list[tuple[str, str, tuple[str, ...] | None]] = [
    ("wetland_south_ng", "Wetland_Data.zip", None),
    ("eo4forest_lagos_ogun", "AOI_boundaries.zip", None),
    ("eo4forest_lagos_ogun", "TrainingAndValidationSamples.zip", None),
    ("eo4forest_lagos_ogun", "ClassificationMaps.zip",
     (".txt", ".clr", "AOI0_2023-12.tif")),
    ("hydrobasins_af", "hybas_af_lev06_v1c.zip", None),
    ("hydrobasins_af", "hybas_af_lev08_v1c.zip", None),
    ("hadejia_flood", "hadejia.zip", None),
]


def safe_extract(zip_path: Path, dest: Path, suffixes: tuple[str, ...] | None = None) -> list[str]:
    out = []
    with zipfile.ZipFile(zip_path) as zf:
        for m in zf.namelist():
            p = PurePosixPath(m)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError(f"unsafe member {m!r} in {zip_path}")
            if suffixes and not m.endswith(suffixes):
                continue
            target = dest / m
            if target.exists() and not m.endswith("/") and target.stat().st_size == zf.getinfo(m).file_size:
                continue
            zf.extract(m, dest)
            out.append(m)
    return out


def extract_all() -> dict[str, int | str]:
    report = {}
    for sid, name, members in PLAN:
        z = RAW_DIR / sid / name
        if not z.exists():
            report[f"{sid}/{name}"] = "missing (fetch first)"
            continue
        report[f"{sid}/{name}"] = len(safe_extract(z, RAW_DIR / sid / "extracted", members))
    return report
