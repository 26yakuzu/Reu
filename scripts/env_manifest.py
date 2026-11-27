"""Record the software environment -> artifacts/manifests/environment.json"""
import json
import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import distributions

from terrasense.config import MANIFEST_DIR

import rasterio

MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "python": sys.version,
       "platform": platform.platform(), "gdal": rasterio.__gdal_version__,
       "packages": dict(sorted((d.metadata["Name"], d.version) for d in distributions()))}
(MANIFEST_DIR / "environment.json").write_text(json.dumps(out, indent=2))
print("wrote", MANIFEST_DIR / "environment.json")
