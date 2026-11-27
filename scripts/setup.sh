#!/usr/bin/env bash
# One-step setup for TerraSense Nigeria.
#   bash scripts/setup.sh lite   # ~100 MB, a few minutes: map, Lagos/Ogun land cover, basins, field sites
#   bash scripts/setup.sh full   # ~3 GB, ~1 hour: adds Hadejia floods, national WOfS water history, SoilGrids
set -euo pipefail
MODE="${1:-lite}"
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"

echo "==> Python: $($PY --version)"
$PY -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Python 3.11 or newer is required")'

if [ ! -d .venv ]; then
  echo "==> Creating virtual environment (.venv)"
  $PY -m venv .venv
fi
# shellcheck disable=SC1091
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; else . .venv/Scripts/activate; fi

echo "==> Installing dependencies"
pip install -q --upgrade pip
pip install -q -r requirements.lock.txt
pip install -q -e ".[app,dev]" --no-deps

echo "==> Downloading data ($MODE)"
if [ "$MODE" = "full" ]; then
  python -I scripts/fetch.py --include-large
  python -I scripts/extract.py
  python -I scripts/fetch_wofs.py
  python -I scripts/fetch_soilgrids.py
else
  python -I scripts/fetch.py
  python -I scripts/extract.py
fi

echo "==> Preparing layers"
python -I scripts/prepare.py

echo "==> Running tests"
python -m pytest -q || echo "(some tests failed — see output above)"

cat <<MSG

Setup complete ($MODE). Start the app with:

    bash scripts/run_app.sh          # dashboard -> http://localhost:8501
    bash scripts/run_app.sh api      # API       -> http://127.0.0.1:8000/docs
MSG
