"""ASGI config for the DefexVision project."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "defexvision.settings")

application = get_asgi_application()
