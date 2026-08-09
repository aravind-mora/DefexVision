#!/usr/bin/env bash
# DefexVision - one-time setup for a fresh local machine (laptop/PC).
# Creates a virtualenv, installs deps, prepares the SQL database, and copies
# .env.example -> .env if missing.
#
# Usage:  bash setup.sh
# Then:   bash run.sh   (starts Flask API + Django, then open http://localhost:8000)
set -e
cd "$(dirname "$0")"

PY_BIN="${PYTHON:-python3}"

echo "==> Checking Python (need 3.9+)"
if ! command -v "$PY_BIN" >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.9+ first."; exit 1
fi
"$PY_BIN" --version

echo "==> Creating virtual environment (.venv)"
if [ ! -d ".venv" ]; then
  "$PY_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Upgrading pip"
pip install --upgrade pip

echo "==> Installing dependencies"
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "==> Creating .env from .env.example"
  cp .env.example .env
fi

echo "==> Running database migrations"
python manage.py migrate

echo "============================================================="
echo " Setup complete!"
echo " Next step: run your app with:   bash run.sh"
echo " Then open:                      http://localhost:8000"
echo "============================================================="
