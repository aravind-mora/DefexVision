"""
Defect taxonomy for DefexVision (mouse chip / PCB inspection).

This mirrors the logic used in the project's reference detector script exactly:

    defect_classes = [
        "IC-defect", "LED-defect", "Mouse-click defect",
        "Mouse-scrolldefect", "Resistor-defect", "capacitor-defect"
    ]
    category = "Defect" if class_name in defect_classes else "Non-Defect"
    color    = (0, 0, 255) if category == "Defect" else (0, 255, 0)

Anything the model returns that is NOT in defect_classes is treated as
"Non-Defect" (green, pass). Anything in defect_classes is "Defect" (red, fail).
"""
from __future__ import annotations

# EXACT defect-class list from the project reference script.
DEFECT_CLASSES = [
    "IC-defect",
    "LED-defect",
    "Mouse-click defect",
    "Mouse-scrolldefect",
    "Resistor-defect",
    "capacitor-defect",
]

# BGR colours, matching the reference script.
COLOR_DEFECT = (0, 0, 255)        # red    -> cv2 (0,0,255) is red in BGR
COLOR_NON_DEFECT = (0, 255, 0)    # green  -> cv2 (0,255,0) is green in BGR

# Defect-class -> {label, color(BGR), severity, description}
# (IDs are just for internal indexing; classification is done by label.)
DEFECTS: dict[int, dict] = {
    i: {
        "label": name,
        "color": COLOR_DEFECT,
        "severity": "major",            # in the defect list -> a defect
        "description": f"{name}: detected defect region.",
    }
    for i, name in enumerate(DEFECT_CLASSES)
}

_DEFECTS_BY_LABEL = {d["label"]: {**d, "id": cid} for cid, d in DEFECTS.items()}

# Normalised (lowercase, whitespace-collapsed) lookup so we are tolerant of
# minor case / spacing differences between model output and this list.
_NORM_BY_LABEL = {}
for cid, d in DEFECTS.items():
    key = " ".join(d["label"].split()).lower()
    _NORM_BY_LABEL[key] = {**d, "id": cid}


def _norm(s: str) -> str:
    return " ".join(str(s).split()).lower()


def is_defect(label: str) -> bool:
    """True if the model label is a defect class (else Non-Defect / pass)."""
    if not label:
        return False
    if label in _NORM_BY_LABEL:
        return True
    # fall back to exact string comparison too
    return label in DEFECT_CLASSES


def category_of(label: str) -> str:
    """'Defect' or 'Non-Defect', exactly like the reference script."""
    return "Defect" if is_defect(label) else "Non-Defect"


def info_for(class_id: int) -> dict:
    return DEFECTS.get(int(class_id), {
        "label": f"class-{class_id}",
        "color": COLOR_DEFECT,
        "severity": "major",
        "description": "Unknown defect class.",
    })


def info_for_label(label: str) -> dict:
    """Look up defect metadata by label. Unknown labels -> Non-Defect (green)."""
    if not label:
        return {
            "label": "unknown",
            "color": COLOR_NON_DEFECT,
            "severity": "none",
            "description": "No defect - pass.",
            "id": -1,
        }
    entry = _NORM_BY_LABEL.get(_norm(label))
    if entry is None:
        return {
            "label": str(label),
            "color": COLOR_NON_DEFECT,      # not in defect list -> Non-Defect
            "severity": "none",
            "description": "Non-Defect - pass.",
            "id": -1,
        }
    return entry


def label_to_id(label: str) -> int | None:
    entry = _NORM_BY_LABEL.get(_norm(label))
    return entry["id"] if entry else None


def all_classes() -> list:
    return [{"id": k, **v} for k, v in sorted(DEFECTS.items())]