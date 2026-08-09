"""
Django settings for the DefexVision web platform.

DefexVision: AI-powered defect detection for computer mouse chips.

Web stack used:
  - Django  (primary web framework / rich frontend / SQL ORM)
  - Flask   (separate microservice exposing the ML inference API)
  - SQL     (SQLite by default; switch to PostgreSQL via .env)
  - NoSQL   (MongoDB for image-analysis metadata, with local fallback)
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


def _b(name, default):
    return os.environ.get(name, default)


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = _b("DJANGO_SECRET_KEY", "django-insecure-dev-defexvision")
DEBUG = _b("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in _b(
        "DJANGO_ALLOWED_HOSTS",
        "localhost,127.0.0.1,0.0.0.0,testserver",
    ).split(",")
    if h.strip()
]
if DEBUG:
    # During development / preview the host header is arbitrary
    # (e.g. the Arena preview host). Allow any host while debugging.
    ALLOWED_HOSTS.append("*")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "scanner.apps.ScannerConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "defexvision.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "defexvision.wsgi.application"

# ---------------------------------------------------------------------------
# Database (SQL)
# ---------------------------------------------------------------------------
# Default to SQLite. Override with DATABASE_* env vars for PostgreSQL.
DATABASES = {
    "default": {
        "ENGINE": _b("DATABASE_ENGINE", "django.db.backends.sqlite3"),
        "NAME": _b("DATABASE_NAME", str(BASE_DIR / "db.sqlite3")),
        "USER": _b("DATABASE_USER", ""),
        "PASSWORD": _b("DATABASE_PASSWORD", ""),
        "HOST": _b("DATABASE_HOST", ""),
        "PORT": _b("DATABASE_PORT", ""),
    }
}

# ---------------------------------------------------------------------------
# Auth / passwords
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DefexVision application settings
# ---------------------------------------------------------------------------
DEFEXVISION = {
    # flask | demo   -> use Flask microservice, or run without a real model
    "INFERENCE_MODE": _b("INFERENCE_MODE", "flask"),
    "FLASK_API_URL": _b("FLASK_API_URL", "http://127.0.0.1:5001"),
    "MODEL_PATH": _b("MODEL_PATH", "models/yolo8m (1).pt"),
    "MODEL_CONF": float(_b("MODEL_CONF", "0.25")),
    "MODEL_IOU": float(_b("MODEL_IOU", "0.45")),
    # raw      -> feed the raw image to the model (matches reference script)
    # enhanced -> crop/denoise/enhance/deskew pipeline before inference
    "PREPROCESS_MODE": _b("PREPROCESS_MODE", "raw"),
    "MONGO_URI": _b("MONGO_URI", "mongodb://localhost:27017"),
    "MONGO_DB": _b("MONGO_DB", "defexvision"),
}