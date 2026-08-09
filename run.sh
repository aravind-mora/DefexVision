#!/usr/bin/env bash
# DefexVision quick-start: migrate, start Flask API + Django dev server.
set -e
cd "$(dirname "$0")"
PY="${PY:-.venv/bin/python}"
[ -x "$PY" ] || PY=python3

echo "==> Migrating SQL database"
"$PY" manage.py migrate --noinput

echo "==> Starting Flask inference API (port 5001)"
"$PY" inference_api/app.py &
FLASK_PID=$!
trap "kill $FLASK_PID 2>/dev/null" EXIT
sleep 2

echo "==> Starting Django (http://0.0.0.0:8000)"
"$PY" manage.py runserver 0.0.0.0:8000
