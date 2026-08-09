"""
DefexVision - download the YOLOv8 model weights.

The model file is too big for GitHub, so it's distributed via cloud storage
(Google Drive / Dropbox / any direct URL). This helper downloads it into the
`models/` folder so the app can use it.

Usage:
    python download_model.py https://drive.google.com/your-link
    # or
    MODEL_URL="https://..." python download_model.py

Google Drive links are handled with gdown (which follows Drive's confirmation
page reliably); other direct URLs use urllib. The temp file is written inside
`models/` so os.replace() never hits a cross-device error.
"""
import os
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
DEFAULT_NAME = "yolo8m (1).pt"


def _gdown_available() -> bool:
    try:
        import gdown  # noqa: F401
        return True
    except ImportError:
        return False


def download(url: str, dest_name: str | None = None) -> Path:
    MODELS_DIR.mkdir(exist_ok=True)
    dest = MODELS_DIR / (dest_name or DEFAULT_NAME)
    tmp = str(dest) + ".part"

    print(f"Downloading model from:\n  {url}\nTo:\n  {dest}")

    if "drive.google.com" in url and _gdown_available():
        # gdown handles Google Drive confirmation pages reliably. Use its
        # Python API so we don't depend on the gdown CLI being on PATH.
        import gdown
        gdown.download(url, tmp, quiet=False)
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as out:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                out.write(chunk)

    # If the file looks like HTML (e.g. a Drive confirmation page slipped
    # through via urllib), flag it instead of saving a broken model.
    try:
        head = open(tmp, "rb").read(4)
        if head.lstrip().startswith(b"<"):
            os.remove(tmp)
            raise RuntimeError(
                "download returned an HTML page, not a model file. "
                "Install gdown (pip install gdown) or make sure the link is "
                "a public direct link."
            )
    except FileNotFoundError:
        pass

    os.replace(tmp, dest)
    size = dest.stat().st_size / 1e6
    print(f"Done. Model saved: {dest} ({size:.1f} MB)")
    return dest


def main():
    url = None
    name = None
    args = [a for a in sys.argv[1:] if not a.startswith("--name=")]
    for a in sys.argv[1:]:
        if a.startswith("--name="):
            name = a.split("=", 1)[1]
    if args:
        url = args[0]
    if not url:
        url = os.environ.get("MODEL_URL")
    if not url:
        print(__doc__)
        sys.exit(1)
    download(url, name)


if __name__ == "__main__":
    main()