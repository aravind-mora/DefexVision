from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("scan/", views.scan, name="scan"),
    path("history/", views.history, name="history"),
    path("inspection/<int:pk>/", views.detail, name="detail"),
    path("inspection/<int:pk>/delete/", views.delete_inspection, name="delete_inspection"),
    path("health/", views.health, name="health"),
]
