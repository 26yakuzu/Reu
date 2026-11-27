#!/usr/bin/env bash
# Start the dashboard (default) or the API.
#   bash scripts/run_app.sh        -> http://localhost:8501
#   bash scripts/run_app.sh api    -> http://127.0.0.1:8000/docs
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; else . .venv/Scripts/activate; fi
if [ "${1:-app}" = "api" ]; then
  exec uvicorn terrasense.api.main:app --host 127.0.0.1 --port 8000
else
  exec streamlit run app/streamlit_app.py --server.port 8501
fi
