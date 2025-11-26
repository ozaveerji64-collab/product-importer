# app/tasks.py
import os
import json
from celery import Celery
from sqlalchemy import text
from .database import engine
from dotenv import load_dotenv
import redis

load_dotenv()

BROKER_URL = os.environ.get("BROKER_URL", "redis://redis:6379/1")
RESULT_BACKEND = os.environ.get("RESULT_BACKEND", "redis://redis:6379/2")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery("tasks", broker=BROKER_URL, backend=RESULT_BACKEND)

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def set_progress(task_id: str, percent: int, status: str, meta=None):
    """
    Store progress information for a given task in Redis.
    Frontend /sse/progress/{task_id} reads this.
    """
    key = f"import_progress:{task_id}"
    payload = {"percent": percent, "status": status, "meta": meta or {}}
    r.set(key, json.dumps(payload))
    r.expire(key, 3600)  # auto-clean after 1 hour


@celery_app.task(bind=True)
def import_csv_task(self, filepath: str, user_provided_active: bool = True):
    """
    Efficient CSV import:
    1. COPY CSV into a persistent staging table (staging_products)
    2. Deduplicate by case-insensitive SKU
    3. Upsert into products table using ON CONFLICT on sku_normalized
    """
    task_id = self.request.id

    try:
        set_progress(task_id, 0, "starting")

        # 1) Ensure staging table exists, has required columns, and is empty
        set_progress(task_id, 5, "preparing_staging_table")
        with engine.begin() as conn:
            # Base table
            conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS staging_products (
                    sku text,
                    name text,
                    description text,
                    price text
                );
                """
                )
            )
            # Ensure id column exists (used for dedup ordering)
            conn.execute(
                text(
                    """
                ALTER TABLE staging_products
                ADD COLUMN IF NOT EXISTS id serial;
                """
                )
            )
            # Ensure sku_normalized column exists
            conn.execute(
                text(
                    """
                ALTER TABLE staging_products
                ADD COLUMN IF NOT EXISTS sku_normalized text;
                """
                )
            )
            # Clear previous data
            conn.execute(text("TRUNCATE TABLE staging_products;"))

        # 2) COPY CSV into staging_products using raw connection
        set_progress(task_id, 10, "copying_csv")
        raw_conn = engine.raw_connection()
        cursor = raw_conn.cursor()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                cursor.copy_expert(
                    "COPY staging_products (sku,name,description,price) "
                    "FROM STDIN WITH CSV HEADER",
                    f,
                )
            raw_conn.commit()
        finally:
            cursor.close()
            raw_conn.close()

        set_progress(task_id, 50, "copied_to_staging")

        # 3) Deduplicate rows in staging by lower(sku)
        #    Keep the last row (highest id) for each case-insensitive SKU
        set_progress(task_id, 60, "deduplicating_staging")
        with engine.begin() as conn:
            # Populate normalized SKU
            conn.execute(
                text(
                    """
                UPDATE staging_products
                SET sku_normalized = lower(sku);
                """
                )
            )
            # Delete duplicates where same sku_normalized, keep max(id)
            conn.execute(
                text(
                    """
                DELETE FROM staging_products a
                USING staging_products b
                WHERE a.sku_normalized = b.sku_normalized
                  AND a.id < b.id;
                """
                )
            )

        set_progress(task_id, 75, "upserting_products")

        # 4) Upsert from staging_products into products
        upsert_sql = """
        INSERT INTO products (sku, sku_normalized, name, description, price, active, metadata)
        SELECT
            sku,
            sku_normalized,
            name,
            description,
            price,
            :active,
            '{}'::jsonb
        FROM staging_products
        ON CONFLICT (sku_normalized) DO UPDATE SET
            sku         = EXCLUDED.sku,
            name        = EXCLUDED.name,
            description = EXCLUDED.description,
            price       = EXCLUDED.price,
            active      = EXCLUDED.active,
            metadata    = EXCLUDED.metadata;
        """

        with engine.begin() as conn2:
            conn2.execute(text(upsert_sql), {"active": user_provided_active})

        set_progress(task_id, 95, "upsert_complete")
        set_progress(task_id, 100, "done")

        return {"status": "ok"}

    except Exception as e:
        # Push a clear error to Redis so UI can show it
        set_progress(
            task_id,
            100,
            "error",
            {
                "detail": str(e),
            },
        )
        # Re-raise so the worker logs still show full traceback
        raise
