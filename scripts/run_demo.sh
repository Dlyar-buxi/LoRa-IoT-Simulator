#!/usr/bin/env bash
# LoRa-IoT-Simulator — local automated demo (headless).
#
# Runs a short headless experiment, records it to demo.db, and exports a
# Markdown report — all WITHOUT starting the web server. For the interactive
# dashboard, use `docker compose up --build` or `python -m backend.main`.
#
# Works on Linux/macOS and in Git Bash on Windows (detects the venv path).
set -euo pipefail

cd "$(dirname "$0")/.."

# Locate a Python interpreter (prefer an existing venv, else system python).
if [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
elif [ -x "venv/Scripts/python.exe" ]; then
  PY="venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

echo "==> Using interpreter: $PY"

echo "==> Running headless demo experiment (20 nodes, area 400, seed 1, 60s) ..."
"$PY" scripts/generate_experiment.py --nodes 20 --area 400 --seed 1 --duration 60 --gateways 2 --db demo.db

echo "==> Exporting report ..."
"$PY" scripts/export_report.py --db demo.db --out demo_report.md

echo ""
echo "Done. Artifacts:"
echo "  - demo.db         (SQLite experiment store)"
echo "  - demo_report.md  (Markdown report)"
echo ""
echo "To launch the interactive dashboard instead:"
echo "  docker compose up --build     # or: $PY -m backend.main"
