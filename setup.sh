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

# ---- Auto-download the model if a MODEL_URL is configured --------------
# Load MODEL_URL / MODEL_PATH from .env so new users get the model without
# having to find the file. If the download fails, we still continue (the app
# can run in demo mode) but tell the user.
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

MODEL_PATH="${MODEL_PATH:-models/yolo8m (1).pt}"
if [ ! -f "$MODEL_PATH" ]; then
  if [ -n "$MODEL_URL" ]; then
    echo "==> Downloading model (this can take a minute)..."
    if python download_model.py "$MODEL_URL"; then
      echo "==> Model downloaded."
    else
      echo "==> [WARN] Model download failed. The app will run in DEMO mode."
      echo "    You can retry later with: python download_model.py \"\$MODEL_URL\""
    fi
  else
    echo "==> [WARN] No MODEL_URL set and no model found. Running in DEMO mode."
  fi
else
  echo "==> Model found: $MODEL_PATH"
fi

echo "============================================================="
echo " Setup complete!"
echo " Next step: run your app with:   bash run.sh"
echo " Then open:                      http://localhost:8000"
echo "============================================================="