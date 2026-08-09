"""
SQL models (Django ORM) for DefexVision inspections.

Relational data lives here: users, inspection jobs and per-defect records.
Rich image-analysis JSON is stored in NoSQL (MongoDB) via nosql_store.py.
"""
from django.contrib.auth.models import User
from django.db import models


class Inspection(models.Model):
    """One image inspection job."""

    class Status(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        PROCESSING = "processing", "Processing"

    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="inspections"
    )
    filename = models.CharField(max_length=255)
    # original upload
    image = models.ImageField(upload_to="uploads/")
    # final annotated result (drawn on the crop)
    result_image = models.ImageField(upload_to="results/", null=True, blank=True)
    # annotated original full-frame
    result_original = models.ImageField(upload_to="results/", null=True, blank=True)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PROCESSING
    )
    defects_found = models.IntegerField(default=0)
    total_detections = models.IntegerField(default=0)
    max_confidence = models.FloatField(default=0.0)
    inference_mode = models.CharField(max_length=64, default="")
    chip_bbox = models.CharField(max_length=64, null=True, blank=True)
    summary_json = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Inspection #{self.pk} - {self.filename}"

    @property
    def is_fail(self):
        return self.status == self.Status.FAIL


class DetectedDefect(models.Model):
    """One detected defect box (SQL) - rendered and auditable per inspection."""

    inspection = models.ForeignKey(
        Inspection, on_delete=models.CASCADE, related_name="detected_defects"
    )
    class_id = models.IntegerField()
    label = models.CharField(max_length=64)
    confidence = models.FloatField()
    bbox = models.CharField(max_length=128)  # x1,y1,x2,y2 on the deskewed crop
    severity = models.CharField(max_length=32, default="unknown")
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.label} @ {self.inspection_id}"
