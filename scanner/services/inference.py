"""
Inference engine for DefexVision.

Two modes are supported (set INFERENCE_MODE in .env):

  * flask : POST the preprocessed (model-ready) image to the Flask
            microservice, which loads the real YOLOv8 weights and returns
            detections.
  * demo  : no real model needed. Produces realistic synthetic detections so
            you can develop / preview the whole flow. Drop your real
            "yolo8m (1).pt" weights into models/ and switch to flask mode
            for genuine inference.

Detections are rendered onto the (deskewed) chip crop to produce the final
annotated result image shown in the UI.
"""
from __future__ import annotations

import os
import random
import urllib.request

import cv2
import numpy as np
from django.conf import settings

from . import defects
from .preprocess import PreprocessResult


def _cfg(key, default):
    return settings.DEFEXVISION.get(key, default)


def _info_for(detection: dict) -> dict:
    """
    Metadata for a detection: prefer lookup by the model's label (so colours /
    severities stay correct even if class-index order differs), fall back to
    the class_id mapping. Unknown labels classify as Non-Defect (green).
    """
    label = detection.get("label")
    if label:
        return defects.info_for_label(label)
    return defects.info_for(detection.get("class_id", -1))


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def draw_detections(image_rgb: np.ndarray, detections: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """
    Draw boxes + labels onto the image (RGB numpy). Also returns the
    *annotated* BGR copy used for the side-by-side "raw vs annotated".
    """
    annotated = image_rgb.copy()
    h, w = image_rgb.shape[:2]

    for d in detections:
        x1, y1, x2, y2 = d["bbox"]  # absolute pixels on this image
        conf = d["confidence"]
        info = _info_for(d)
        label = d.get("label") or info["label"]

        # Exact colour logic from the reference script:
        #   red for Defect, green for Non-Defect
        category = defects.category_of(label)
        color_bgr = defects.COLOR_DEFECT if category == "Defect" else defects.COLOR_NON_DEFECT

        # clamp boxes to image bounds
        x1 = int(max(0, min(w, x1)))
        y1 = int(max(0, min(h, y1)))
        x2 = int(max(0, min(w, x2)))
        y2 = int(max(0, min(h, y2)))

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color_bgr, 3)

        text = f"{label} ({conf:.2f})"
        cv2.putText(annotated, text, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_bgr, 2)

    return annotated


def annotate_original(original_rgb: np.ndarray, detections: list[dict]) -> np.ndarray:
    """Draw detections onto the ORIGINAL full image (for the 'raw' tab)."""
    return draw_detections(original_rgb, detections)


# ---------------------------------------------------------------------------
# Real inference via Flask microservice
# ---------------------------------------------------------------------------
def _flask_predict(model_input_rgb: np.ndarray) -> list[dict]:
    url = _cfg("FLASK_API_URL", "http://127.0.0.1:5001") + "/predict"
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(model_input_rgb, cv2.COLOR_RGB2BGR),
                           [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    body = buf.tobytes()

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json
        payload = json.loads(resp.read().decode("utf-8"))
    detections = []
    for item in payload.get("detections", []):
        detections.append({
            "class_id": int(item["class_id"]),
            "label": item["label"],
            "confidence": float(item["confidence"]),
            "bbox": [float(v) for v in item["bbox"]],  # xyxy absolute on 640 image
        })
    return detections


# ---------------------------------------------------------------------------
# Demo mode - synthetic detections
# ---------------------------------------------------------------------------
def _demo_predict(model_input_rgb: np.ndarray) -> list[dict]:
    h, w = model_input_rgb.shape[:2]
    n = random.randint(1, 4)
    defect_ids = [0, 1, 2, 3, 4, 5]  # the defect classes (exclude Non-Defect=6)
    detections = []
    for _ in range(n):
        class_id = random.choice(defect_ids)
        bw, bh = random.randint(int(0.08 * w), int(0.22 * w)), \
                 random.randint(int(0.08 * h), int(0.22 * h))
        x = random.randint(0, w - bw - 1)
        y = random.randint(0, h - bh - 1)
        info = defects.info_for(class_id)
        detections.append({
            "class_id": class_id,
            "label": info["label"],
            "confidence": round(random.uniform(0.72, 0.98), 3),
            "bbox": [float(x), float(y), float(x + bw), float(y + bh)],
        })
    return detections


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def run_inference(result: PreprocessResult, job_dir: str) -> dict:
    """
    Run detection on a PreprocessResult and write all output files.

    Returns a dict with:
      detections, summary, files {annotated, annotated_original}
    """
    mode = _cfg("INFERENCE_MODE", "flask")

    if mode == "flask":
        try:
            detections = _flask_predict(result.model_input)
        except Exception:
            # If the Flask API isn't running, fall back to demo with a flag
            detections = _demo_predict(result.model_input)
            mode = "demo (flask unavailable)"
    else:
        detections = _demo_predict(result.model_input)

    # Render annotated images
    annotated = draw_detections(result.deskewed, detections)
    annotated_original = draw_detections(result.original_bgr.copy(), _scale_boxes(
        detections, result.deskewed.shape[:2], result.original_bgr.shape[:2]))

    # Save outputs
    def _write(img_rgb, name):
        path = os.path.join(job_dir, name)
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR),
                               [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        if ok:
            with open(path, "wb") as f:
                f.write(buf.tobytes())
        return path

    files = {
        "annotated": _write(annotated, "result_annotated.jpg"),
        "annotated_original": _write(annotated_original, "result_original.jpg"),
    }

    # Summary / statistics
    counts = {}
    for d in detections:
        counts[d["label"]] = counts.get(d["label"], 0) + 1
    n_defects = sum(1 for d in detections if defects.is_defect(d.get("label", "")))
    passed = n_defects == 0
    max_conf = max((d["confidence"] for d in detections), default=0.0)

    summary = {
        "total_detections": len(detections),
        "defects_found": n_defects,
        "passed": passed,
        "max_confidence": round(max_conf, 3),
        "counts": counts,
    }

    return {
        "mode": mode,
        "detections": detections,
        "summary": summary,
        "files": files,
    }


def _scale_boxes(detections, from_shape, to_shape):
    """Scale detections drawn on the deskewed crop to the original image size."""
    fh, fw = from_shape[:2]
    th, tw = to_shape[:2]
    sx, sy = tw / fw, th / fh
    out = []
    for d in detections:
        x1, y1, x2, y2 = d["bbox"]
        out.append({**d, "bbox": [x1 * sx, y1 * sy, x2 * sx, y2 * sy]})
    return out