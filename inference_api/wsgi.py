"""
WSGI entry point for the Flask inference API (for gunicorn).
Run with:
    gunicorn "inference_api.wsgi:app" --bind 0.0.0.0:5001
"""
import sys
from pathlib import Path

# ensure the project root is importable (so `scanner` package resolves)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from inference_api.app import app  # noqa: E402

application = app
