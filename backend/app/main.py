import os
import json
import uuid
import time

import redis
import requests
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends,
    Query,
    Form,
)
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import SessionLocal, engine, Base
from . import models, crud, schemas, tasks, utils

load_dotenv()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Product Importer")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ---- Redis Connection (Upstash compatible) ----
REDIS_URL = os.environ.get("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not configured")

# Upstash requires SSL
r = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    ssl=True
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def index():
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# -------------------- UPLOAD + PROGRESS --------------------
@app.post("/upload")
async def upload_csv(file: UploadFile = File(...), active: bool = Form(True)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    saved = utils.save_upload_file(
        file.file, filename=f"{uuid.uuid4().hex}_{file.filename}"
    )
    task = tasks.import_csv_task.apply_async(args=[saved, active])
    return {"task_id": task.id}


@app.get("/sse/progress/{task_id}")
def sse_progress(task_id: str):
    def event_stream():
        key = f"import_progress:{task_id}"
        last = None
        while True:
            val = r.get(key)
            if val != last:
                last = val
                yield f"data: {val}\n\n"
                if val:
                    try:
                        parsed = json.loads(val)
                        if parsed.get("status") in ("done", "error"):
                            break
                    except Exception:
                        pass
            time.sleep(0.5)
    return StreamingResponse(event_stream(), media_type="text/event-stream")


# -------------------- PRODUCTS CRUD --------------------
@app.get("/api/products")
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    sku: str | None = None,
    name: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
):
    skip = (page - 1) * page_size
    filters = {"sku": sku, "name": name, "active": active}
    items, total = crud.list_products(db, skip=skip, limit=page_size, filters=filters)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.delete("/api/products")
def delete_all(db: Session = Depends(get_db)):
    n = crud.delete_all_products(db)
    return {"deleted": n}


# -------------------- WEBHOOKS --------------------
def ensure_webhook_table(db: Session):
    db.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS webhooks (
            id serial PRIMARY KEY,
            url text NOT NULL,
            events jsonb NOT NULL,
            enabled boolean NOT NULL DEFAULT true
        )
        """
        )
    )


@app.post("/api/webhooks")
def create_webhook(payload: dict, db: Session = Depends(get_db)):
    ensure_webhook_table(db)

    url = payload.get("url")
    events = payload.get("events", [])
    enabled = payload.get("enabled", True)

    if not url:
        raise HTTPException(status_code=400, detail="url required")

    res = db.execute(
        text(
            """
        INSERT INTO webhooks (url, events, enabled)
        VALUES (:url, CAST(:events AS jsonb), :enabled)
        RETURNING id
        """
        ),
        {"url": url, "events": json.dumps(events), "enabled": bool(enabled)},
    )
    db.commit()
    return {"id": res.fetchone()[0]}


@app.get("/api/webhooks")
def list_webhooks(db: Session = Depends(get_db)):
    ensure_webhook_table(db)
    rows = db.execute(
        text(
            """
        SELECT id, url, events::text, enabled
        FROM webhooks
        ORDER BY id DESC
        """
        )
    ).fetchall()

    return [
        {
            "id": r[0],
            "url": r[1],
            "events": json.loads(r[2]),
            "enabled": r[3],
        }
        for r in rows
    ]


@app.put("/api/webhooks/{webhook_id}")
def update_webhook(webhook_id: int, payload: dict, db: Session = Depends(get_db)):
    ensure_webhook_table(db)

    fields = []
    params = {"id": webhook_id}

    if "url" in payload:
        fields.append("url = :url")
        params["url"] = payload["url"]

    if "events" in payload:
        fields.append("events = CAST(:events AS jsonb)")
        params["events"] = json.dumps(payload["events"])

    if "enabled" in payload:
        fields.append("enabled = :enabled")
        params["enabled"] = bool(payload["enabled"])

    if not fields:
        return {"updated": False}

    q = "UPDATE webhooks SET " + ", ".join(fields) + " WHERE id = :id"
    db.execute(text(q), params)
    db.commit()
    return {"updated": True}


@app.delete("/api/webhooks/{webhook_id}")
def delete_webhook(webhook_id: int, db: Session = Depends(get_db)):
    ensure_webhook_table(db)
    res = db.execute(
        text("DELETE FROM webhooks WHERE id = :id RETURNING id"),
        {"id": webhook_id},
    ).fetchone()
    db.commit()
    if not res:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"deleted": 1}


@app.post("/api/webhooks/test/{webhook_id}")
def test_webhook(webhook_id: int, db: Session = Depends(get_db)):
    ensure_webhook_table(db)
    row = db.execute(
        text("SELECT url, enabled FROM webhooks WHERE id = :id"),
        {"id": webhook_id},
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    url, enabled = row[0], row[1]

    if not enabled:
        raise HTTPException(status_code=400, detail="Webhook disabled")

    payload = {"event": "webhook_test", "source": "product_importer"}
    start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=5)
        duration = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "ok",
            "response_code": resp.status_code,
            "response_time_ms": duration,
        }
    except Exception as e:
        duration = round((time.perf_counter() - start) * 1000, 2)
        raise HTTPException(
            502,
            f"Failed after {duration} ms: {e}",
        )
