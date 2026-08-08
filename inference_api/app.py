"""
DefexVision - Flask inference microservice.

Receives the preprocessed (model-ready) image bytes from Django and returns
detections. Loads the real YOLOv8 weights from models/ when ultralytics is
installed; otherwise returns demo detections so the pipeline stays testable.

Run with:
    .venv/bin/python inference_api/app.py
    (default port 5001)
"""
import io
import os
import random
import sys

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import Flask, jsonify, request

# ensure project root is importable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load configuration from the project's .env file (same as Django).
# This is what makes changes to MODEL_PATH / MODEL_CONF etc. in .env take effect.
load_dotenv(os.path.join(BASE_DIR, ".env"))

from scanner.services import defects  # noqa: E402

app = Flask(__name__)

_model = None
_model_ready = False
_model_error = None
_checked_env = False


def _env():
    """Read inference settings from the environment / .env on demand."""
    return {
        "MODEL_PATH": os.environ.get("MODEL_PATH", "models/yolo8m (1).pt"),
        "MODEL_CONF": float(os.environ.get("MODEL_CONF", "0.25")),
        "MODEL_IOU": float(os.environ.get("MODEL_IOU", "0.45")),
    }


def _load_model():
    """
    Try to load ultralytics YOLO. Gracefully degrades to demo mode.

    Config is read fresh each time a model load is attempted, so a restart
    (or a change made before the first request) always picks up .env values.
    """
    global _model, _model_ready, _model_error, _checked_env
    if _model_ready or _checked_env:
        return _model

    cfg = _env()
    model_path = cfg["MODEL_PATH"]
    model_conf = cfg["MODEL_CONF"]
    model_iou = cfg["MODEL_IOU"]

    if not os.path.exists(model_path):
        # Not found yet -> report it but DON'T cache, so if the user drops the
        # file in later (or fixes .env) the next request picks it up, no restart.
        _model_error = f"model not found at {model_path}"
        return None

    _checked_env = True
    try:
        from ultralytics import YOLO
        _model = YOLO(model_path)
        _model_ready = True
        _model_error = None
        return _model
    except Exception as exc:  # pragma: no cover
        _model_error = f"could not load model: {exc}"
        return None


@app.get("/health")
def health():
    cfg = _env()
    _load_model()
    return jsonify({
        "status": "ok",
        "model_path": cfg["MODEL_PATH"],
        "model_ready": _model_ready,
        "model_error": _model_error,
        "demo_mode": not _model_ready,
    })


@app.post("/predict")
def predict():
    body = request.get_data()
    if not body:
        return jsonify({"error": "no image body"}), 400

    img_bgr = _bytes_to_cv2(body)
    cfg = _env()
    model = _load_model()

    if model is not None:
        results = model.predict(
            source=img_bgr, conf=cfg["MODEL_CONF"], iou=cfg["MODEL_IOU"], verbose=False
        )[0]
        names = results.names
        detections = []
        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            label = names.get(cls_id, f"class-{cls_id}")
            detections.append({
                "class_id": cls_id,
                "label": label,
                "confidence": round(conf, 4),
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
            })
        return jsonify({"mode": "model", "detections": detections,
                        "model_path": cfg["MODEL_PATH"]})

    # --- demo mode fallback (no model available) ---
    h, w = img_bgr.shape[:2]
    n = random.randint(1, 4)
    detections = []
    for _ in range(n):
        class_id = random.choice(list(defects.DEFECTS.keys()))  # real defect classes
        bw = random.randint(int(0.08 * w), int(0.22 * w))
        bh = random.randint(int(0.08 * h), int(0.22 * h))
        x = random.randint(0, w - bw - 1)
        y = random.randint(0, h - bh - 1)
        detections.append({
            "class_id": class_id,
            "label": defects.info_for(class_id)["label"],
            "confidence": round(random.uniform(0.72, 0.98), 3),
            "bbox": [float(x), float(y), float(x + bw), float(y + bh)],
        })
    return jsonify({"mode": "demo", "detections": detections,
                    "model_error": _model_error})


def _bytes_to_cv2(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode image")
    return img


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    print(f"DefexVision Flask inference API on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
