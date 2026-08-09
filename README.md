# DefexVision

**AI-powered defect detection for computer mouse chips.**

> **Defex** (red) + **Vision** (blue) — upload a chip image, it is preprocessed
> with Python/OpenCV, then passed to a **YOLOv8** model which annotates every
> defect (IC, LED, Mouse-click, Mouse-scroll, Resistor, Capacitor defects).
>
> This repo is a **local web app**: anyone can download it and run it on their
> own machine (no deployment needed).

Built with the requested Python stack only:

| Layer     | Technology                                        |
|-----------|---------------------------------------------------|
| Web app   | **Django** (rich frontend, ORM)                   |
| Inference | **Flask** microservice (loads your `yolo8m (1).pt`)|
| SQL       | SQLite (or PostgreSQL via `.env`)                 |
| NoSQL     | MongoDB (auto-fallback to local JSON store)       |
| Processing| **Python** + OpenCV preprocessing pipeline        |

---

## 1) Quick start (run locally)

**Mac / Linux:**
```bash
bash setup.sh     # creates .venv, installs deps, copies .env, migrates DB
bash run.sh       # starts Flask (5001) + Django (8000)
# open http://localhost:8000