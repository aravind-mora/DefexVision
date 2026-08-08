# DefexVision

**AI-powered defect detection for computer mouse chips.**

> **Defex** (red) + **Vision** (blue) — upload a chip image, it is preprocessed
> (crop, denoise, enhance, deskew) with Python/OpenCV, then passed to a
> **YOLOv8** model which annotates every defect (scratches, cracks,
> contamination, solder bridges, …).

Built with the requested Python stack only:

| Layer     | Technology                                        |
|-----------|---------------------------------------------------|
| Web app   | **Django** (rich frontend, ORM)                   |
| Inference | **Flask** microservice (loads your `yolo8m (1).pt`)|
| SQL       | SQLite (or PostgreSQL via `.env`)                 |
| NoSQL     | MongoDB (auto-fallback to local JSON store)       |
| Processing| **Python** + OpenCV preprocessing pipeline        |

---

## 1) Where does my model go?

GitHub blocks files over 100 MB (and warns above 50 MB), so **`yolo8m (1).pt`
(51 MB) is not committed**. Place it at:

```
models/yolo8m (1).pt
```

The `models/` directory and all `*.pt` files are git-ignored, so your weights
stay on your machine. To run *real* inference you also need the optional deps:

```bash
pip install ultralytics torch
```

If the model isn't present (or `ultralytics` isn't installed), the app runs in
**demo mode** — it still exercises the whole pipeline with synthetic detections,
which is perfect for developing and previewing the UI.

## 2) Setup

```bash
# (recommended) virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# optional, for real YOLO inference
pip install ultralytics torch

cp .env.example .env             # adjust as needed
```

## 3) Run

```bash
# 1. Database migrations (SQL)
python manage.py migrate

# 2. (recommended) start the Flask inference microservice
python inference_api/app.py          # -> http://127.0.0.1:5001

# 3. start Django
python manage.py runserver 0.0.0.0:8000
```

Open **http://localhost:8000**, go to **Scan**, upload a chip image.

> No MongoDB running? No problem — the NoSQL store automatically falls back to
> a local JSON document store (you'll see `backend: json` on the dashboard).

## 4) Admin

```bash
python manage.py createsuperuser
```

Then visit `/admin/` to browse inspections and detected defects.

## 5) Configuration (`.env`)

| Var                | Default                  | Meaning                              |
|--------------------|--------------------------|--------------------------------------|
| `INFERENCE_MODE`   | `flask`                  | `flask` (real) or `demo` (synthetic) |
| `FLASK_API_URL`    | `http://127.0.0.1:5001`  | Flask inference endpoint             |
| `MODEL_PATH`       | `models/yolo8m (1).pt`   | path to your weights                 |
| `MODEL_CONF`       | `0.25`                   | YOLO confidence threshold            |
| `MODEL_IOU`        | `0.45`                   | YOLO NMS IoU                         |
| `MONGO_URI` / `MONGO_DB` | local defexvision | NoSQL connection               |
| `DATABASE_*`       | SQLite                  | switch to PostgreSQL for production  |

## 6) How the pipeline works

```
Upload (image)
   │  Python + OpenCV
   ▼
Preprocess: auto-crop chip → denoise → CLAHE enhance → deskew → letterbox 640
   │
   ▼
Inference: Flask API → YOLOv8 (or demo) → detections [{class, conf, bbox}]
   │
   ├──▶ SQL (Inspection + DetectedDefect rows)
   ├──▶ NoSQL (analysis document: stages, timings, detections)
   └──▶ Annotated result images → shown in the UI
```

## 7) Project layout

```
defexvision/        Django project (settings, urls)
scanner/            Django app (models, views, admin)
  services/
    preprocess.py   OpenCV preprocessing pipeline
    inference.py    inference orchestration + rendering
    defects.py      defect taxonomy / colours / demo classes
    nosql_store.py  MongoDB + JSON-fallback document store
inference_api/      Flask microservice (loads the YOLO model)
models/             ← drop yolo8m (1).pt here (git-ignored)
templates/ static/  rich frontend (dark UI, Defex red + Vision blue)
media/              uploads, stage images, results (git-ignored)
```
