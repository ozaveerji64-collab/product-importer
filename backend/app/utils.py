import os
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def save_upload_file(fileobj, filename: str = None):
    if not filename:
        filename = f"{uuid.uuid4().hex}.csv"
    out_path = UPLOAD_DIR / filename
    with open(out_path, "wb") as f:
        while True:
            chunk = fileobj.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return str(out_path)
