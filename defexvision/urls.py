"""Root URL configuration for DefexVision."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("scanner.urls")),
]

# Serve media (uploaded + result images) both in development and production.
# In production, served directly by Django for this app; for heavy use,
# switch MEDIA_URL to a cloud bucket (S3/Cloudinary) instead.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
