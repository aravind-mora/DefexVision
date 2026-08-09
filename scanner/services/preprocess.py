"""
Preprocessing pipeline for DefexVision.

Takes a raw upload of a computer mouse chip / PCB and produces a clean,
normalised image ready for the YOLOv8 model. Each stage is also rendered so
the web UI can show the user exactly what happened:

    Original
      -> Gray
      -> Denoised
      -> Enhanced (CLAHE)
      -> Chip crop (largest rectangle) + deskew
      -> Model-ready resize (640x640)
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

MODEL_INPUT_SIZE = 640  # YOLOv8 default input resolution


def _preprocess_mode() -> str:
    """Preprocessing mode from settings/.env (default: 'raw')."""
    try:
        from django.conf import settings
        return str(settings.DEFEXVISION.get("PREPROCESS_MODE", "raw")).lower()
    except Exception:
        return os.environ.get("PREPROCESS_MODE", "raw").lower()


# Preprocessing mode:
#   "raw"      -> feed the RAW image straight to the model (matches the
#                 reference script's model(frame1), no crop/denoise/enhance).
#   "enhanced" -> run the full pipeline (crop chip, denoise, CLAHE, deskew).
PREPROCESS_MODE = _preprocess_mode()


def _bytes_to_cv2(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode the uploaded image.")
    return img


@dataclass
class PreprocessResult:
    """Carries the raw + visualised stages of preprocessing."""

    original_bgr: np.ndarray
    gray: np.ndarray
    denoised: np.ndarray
    enhanced: np.ndarray
    cropped: np.ndarray            # chip-only crop (still colour)
    deskewed: np.ndarray
    model_input: np.ndarray        # 640x640 letterboxed RGB for the model
    bbox: list[int] | None         # (x,y,w,h) of the detected chip crop
    angle: float = 0.0
    stages: dict = field(default_factory=dict)  # name -> saved file path


def _largest_quad_bbox(image_bgr: np.ndarray):
    """Find the largest likely chip rectangle via contour analysis."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 40, 120)
    # Dilate to close small gaps in the chip outline
    edged = cv2.dilate(edged, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))

    cnts, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, 0.0

    h, w = image_bgr.shape[:2]
    best = None
    best_area = 0.0
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 0.08 * h * w:  # ignore noise / tiny blobs
            continue
        if area > best_area:
            best_area = area
            best = c

    if best is None:
        return None, 0.0

    rect = cv2.minAreaRect(best)
    box = cv2.boxPoints(rect)
    box = box.astype(np.int32)
    x, y, ww, hh = cv2.boundingRect(box)
    return [int(x), int(y), int(ww), int(hh)], float(rect[2])


def _letterbox(img_bgr: np.ndarray, size: int) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    scale = size / max(h, w)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    x0, y0 = (size - nw) // 2, (size - nh) // 2
    canvas[y0 : y0 + nh, x0 : x0 + nw] = resized
    return canvas


def run_pipeline(data: bytes, job_dir: str) -> PreprocessResult:
    """
    Execute the full preprocessing chain for an uploaded image.

    data     : raw image bytes
    job_dir  : directory where stage visuals are written (should exist)
    """
    os.makedirs(job_dir, exist_ok=True)

    # 0. Load / normalise (auto-orient by EXIF only; never alters pixels)
    original = _bytes_to_cv2(data)
    original = _auto_orient(original)

    # 1. Grayscale (used in enhanced mode + displayed as a stage)
    gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)

    # 2. Denoise (bilateral keeps edges while removing noise)
    denoised = cv2.bilateralFilter(original, d=9, sigmaColor=35, sigmaSpace=35)

    # 3. Contrast enhancement with CLAHE on the luminance channel
    lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    if PREPROCESS_MODE == "raw":
        # -------- RAW mode: matches the reference script exactly ----------
        # model(frame1) -> feed the unmodified original to the model. YOLO
        # resizes internally and returns boxes in the ORIGINAL image's
        # coordinates, so detection boxes can be drawn straight on the raw
        # image with no scaling. (Same behaviour as the reference detector.)
        bbox = None
        angle = 0.0
        cropped = enhanced.copy()
        deskewed = original.copy()
        model_input_bgr = original.copy()          # no letterbox, no crop
        model_input_rgb = cv2.cvtColor(model_input_bgr, cv2.COLOR_BGR2RGB)
    else:
        # -------- ENHANCED mode: crop + deskew pipeline -------------------
        # 4. Detect + crop the chip (largest rectangle)
        bbox, angle = _largest_quad_bbox(enhanced)
        cropped = enhanced.copy()
        if bbox is not None:
            x, y, w, h = bbox
            x, y = max(0, x), max(0, y)
            cropped = enhanced[y : y + h, x : x + w]
            # pad slightly so we don't clip the chip edges
            pad = int(0.04 * max(cropped.shape[:2]))
            cropped = cv2.copyMakeBorder(cropped, pad, pad, pad, pad,
                                         cv2.BORDER_CONSTANT, value=(230, 230, 230))
            angle = float(angle)

        # 5. Deskew (straighten) the chip
        deskewed = _deskew(cropped, angle) if bbox is not None else cropped

        # 6. Resize to model input
        model_input_bgr = _letterbox(deskewed, MODEL_INPUT_SIZE)
        model_input_rgb = cv2.cvtColor(model_input_bgr, cv2.COLOR_BGR2RGB)

    result = PreprocessResult(
        original_bgr=original,
        gray=gray,
        denoised=denoised,
        enhanced=enhanced,
        cropped=cropped,
        deskewed=deskewed,
        model_input=model_input_rgb,
        bbox=bbox,
        angle=angle,
    )

    result.stages = {
        "original": _save(cv2.cvtColor(original, cv2.COLOR_BGR2RGB), job_dir, "stage_original.jpg"),
        "gray": _save(_rgb(gray), job_dir, "stage_gray.jpg"),
        "denoised": _save(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB), job_dir, "stage_denoised.jpg"),
        "enhanced": _save(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB), job_dir, "stage_enhanced.jpg"),
        "cropped": _save(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB), job_dir, "stage_cropped.jpg"),
        "deskewed": _save(cv2.cvtColor(deskewed, cv2.COLOR_BGR2RGB), job_dir, "stage_deskewed.jpg"),
        "model_input": _save(model_input_rgb, job_dir, "stage_model_input.jpg"),
    }
    return result


def _auto_orient(img_bgr: np.ndarray) -> np.ndarray:
    """Rotate image according to EXIF orientation from PIL, if available."""
    try:
        pil_img = Image.open(io.BytesIO(cv2.imencode(".jpg", img_bgr)[1].tobytes()))
        exif = pil_img.getexif()
        orient = exif.get(0x0112, 1)
        if orient in (3, 4):
            img_bgr = cv2.rotate(img_bgr, cv2.ROTATE_180)
        elif orient in (6,):
            img_bgr = cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
        elif orient in (8,):
            img_bgr = cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    except Exception:
        pass
    return img_bgr


def _deskew(img_bgr: np.ndarray, angle: float) -> np.ndarray:
    if abs(angle) < 0.3:
        return img_bgr
    h, w = img_bgr.shape[:2]
    center = (w / 2, h / 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img_bgr, m, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def _rgb(bgr_or_gray: np.ndarray) -> np.ndarray:
    if bgr_or_gray.ndim == 2:
        return cv2.cvtColor(bgr_or_gray, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(bgr_or_gray, cv2.COLOR_BGR2RGB)


def _save(rgb: np.ndarray, folder: str, name: str) -> str:
    path = os.path.join(folder, name)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                           [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if ok:
        with open(path, "wb") as f:
            f.write(buf.tobytes())
    return path