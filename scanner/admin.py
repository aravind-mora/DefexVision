from django.contrib import admin

from .models import DetectedDefect, Inspection


class DetectedDefectInline(admin.TabularInline):
    model = DetectedDefect
    extra = 0


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "status", "defects_found", "max_confidence",
                    "inference_mode", "created_at")
    list_filter = ("status", "inference_mode")
    search_fields = ("filename",)
    readonly_fields = ("created_at", "completed_at")
    inlines = [DetectedDefectInline]


@admin.register(DetectedDefect)
class DetectedDefectAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "confidence", "severity", "inspection")
    list_filter = ("severity", "label")
