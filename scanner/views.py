"""Views for the DefexVision web platform."""
import os
import time

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import DetectedDefect, Inspection
from .services import defects
from .services.inference import run_inference
from .services.nosql_store import get_store
from .services.preprocess import run_pipeline

MEDIA_ROOT = settings.MEDIA_ROOT


def _collect_common_stats():
    """Stats shared by the dashboard + home page."""
    total = Inspection.objects.count()
    passed = Inspection.objects.filter(status="pass").count()
    failed = Inspection.objects.filter(status="fail").count()
    defects = DetectedDefect.objects.count()
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "defects": defects,
        "total_ok": total and round(passed / total * 100, 1),
    }


def index(request):
    recent = Inspection.objects.select_related("user")[:6]
    return render(request, "index.html", {
        "recent": recent,
        "stats": _collect_common_stats(),
        "nav": "home",
    })


def dashboard(request):
    inspections = Inspection.objects.select_related("user")[:20]
    stats = _collect_common_stats()

    # severity breakdown from SQL defect records
    sev = {}
    for d in DetectedDefect.objects.all():
        sev[d.severity] = sev.get(d.severity, 0) + 1

    # recent label distribution
    labels = {}
    for d in DetectedDefect.objects.values("label").order_by("-id")[:100]:
        labels[d["label"]] = labels.get(d["label"], 0) + 1

    return render(request, "dashboard.html", {
        "inspections": inspections,
        "stats": stats,
        "severity": sev,
        "labels": labels,
        "nav": "dashboard",
        "nosql_backend": get_store().ping(),
    })


def history(request):
    inspections = Inspection.objects.select_related("user").all()
    return render(request, "history.html", {
        "inspections": inspections,
        "nav": "history",
    })


def detail(request, pk):
    inspection = get_object_or_404(Inspection, pk=pk)
    analysis = get_store().get_analysis(inspection.pk)
    analysis_id = None
    if analysis:
        analysis_id = str(analysis.get("_id", ""))
        analysis = {k: v for k, v in analysis.items() if k != "_id"}

    defect_rows = []
    for d in inspection.detected_defects.all():
        info = defects.info_for_label(d.label)
        defect_rows.append({
            "pk": d.pk, "label": d.label, "confidence": d.confidence,
            "severity": d.severity,
            "color": ",".join(str(v) for v in info["color"]),
        })
    return render(request, "detail.html", {
        "inspection": inspection,
        "defect_rows": defect_rows,
        "analysis": analysis,
        "analysis_id": analysis_id,
        "nav": "history",
    })


@require_http_methods(["GET", "POST"])
def scan(request):
    if request.method == "GET":
        return render(request, "scan.html", {
            "nav": "scan",
            "defect_classes": defects.all_classes(),
        })

    if "image" not in request.FILES:
        messages.error(request, "Please choose an image file first.")
        return redirect("scan")

    upload = request.FILES["image"]
    if upload.size > 25 * 1024 * 1024:
        messages.error(request, "Image too large (max 25MB).")
        return redirect("scan")

    raw_bytes = upload.read()
    inspection = Inspection.objects.create(
        user=request.user if request.user.is_authenticated else None,
        filename=upload.name,
        status=Inspection.Status.PROCESSING,
    )
    inspection.image.save(upload.name, upload)

    try:
        return _process(request, inspection, raw_bytes)
    except Exception as exc:  # pragma: no cover
        inspection.status = Inspection.Status.FAIL
        inspection.save(update_fields=["status"])
        import logging
        logging.getLogger(__name__).exception("scan failed")
        messages.error(request, f"Processing failed: {exc}")
        return redirect("detail", pk=inspection.pk)


def _process(request, inspection: Inspection, raw_bytes: bytes):
    t0 = time.time()
    job_dir = os.path.join(MEDIA_ROOT, "processed", str(inspection.pk))
    os.makedirs(job_dir, exist_ok=True)

    # 1) Preprocessing (python + OpenCV: crop, deskew, enhance, resize)
    result = run_pipeline(raw_bytes, job_dir)
    inspection.chip_bbox = str(result.bbox) if result.bbox else None
    inspection.save(update_fields=["chip_bbox"])

    # 2) Inference (real YOLOv8 via Flask, or demo fallback)
    inference = run_inference(result, job_dir)

    # 3) Persist the annotated result images
    for field_name, src in (
        ("result_image", inference["files"]["annotated"]),
        ("result_original", inference["files"]["annotated_original"]),
    ):
        with open(src, "rb") as f:
            from django.core.files.base import File
            inspection.__getattribute__(field_name).save(
                os.path.basename(src), File(f), save=False
            )

    summary = inference["summary"]
    inspection.defects_found = summary["defects_found"]
    inspection.total_detections = summary["total_detections"]
    inspection.max_confidence = summary["max_confidence"]
    inspection.summary_json = summary
    inspection.inference_mode = str(inference["mode"])
    inspection.status = Inspection.Status.PASS if summary["passed"] else Inspection.Status.FAIL
    inspection.completed_at = timezone.now()
    inspection.save()

    # 4) SQL: individual defect rows (ONLY actual defects - non-defects are
    #    drawn on the image but are not listed in the "Detected defects" list)
    DetectedDefect.objects.filter(inspection=inspection).delete()
    for d in inference["detections"]:
        if not defects.is_defect(d.get("label", "")):
            continue  # skip non-defects in the text list
        info = defects.info_for_label(d.get("label", ""))
        DetectedDefect.objects.create(
            inspection=inspection,
            class_id=d["class_id"],
            label=d["label"],
            confidence=round(d["confidence"], 4),
            bbox=",".join(str(int(v)) for v in d["bbox"]),
            severity=info["severity"],
            description=info["description"],
        )

    # 5) NoSQL: rich analysis document (MongoDB or JSON fallback)
    pipeline_meta = {k: os.path.relpath(v, MEDIA_ROOT) for k, v in result.stages.items()}
    get_store().insert_analysis(
        record_id=inspection.pk,
        image_name=inspection.filename,
        pipeline={**pipeline_meta, "bbox": result.bbox, "angle": round(result.angle, 2),
                  "duration_ms": int((time.time() - t0) * 1000)},
        detections=inference["detections"],
        summary=summary,
        extra={"mode": inference["mode"]},
    )

    return redirect("detail", pk=inspection.pk)


def delete_inspection(request, pk):
    inspection = get_object_or_404(Inspection, pk=pk)
    inspection.delete()
    messages.success(request, "Inspection deleted.")
    return redirect("history")


def health(request):
    store = get_store()
    return JsonResponse({
        "status": "ok",
        "sql_records": Inspection.objects.count(),
        "nosql_backend": store.ping(),
        "inference_mode": settings.DEFEXVISION.get("INFERENCE_MODE"),
        "flask_api": settings.DEFEXVISION.get("FLASK_API_URL"),
    })
