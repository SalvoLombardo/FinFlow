import json
import logging
from collections import defaultdict

import redis
from sqlalchemy import text

from celery_app.config import app
from celery_app.db import User, get_session
from celery_app.settings import worker_settings

logger = logging.getLogger(__name__)

CACHE_TTL = 8 * 24 * 3600  # 8 days — covers a full weekly cycle with 1-day safety margin
TOP_N = 3
CACHE_DB = 2  # Redis DB: 0=broker, 1=results, 2=pattern cache


def _redis_client() -> redis.Redis:
    base_url = worker_settings.CELERY_BROKER_URL.rsplit("/", 1)[0]
    return redis.from_url(f"{base_url}/{CACHE_DB}", decode_responses=True)


def _compute_patterns_for_user(user_id: str) -> dict[str, list[str]]:
    """
    Query transactions for one user and return a slot-map of top-N categories.
    Slot key: "{dow}_{hour_bucket}"
      - dow        : 0=Sunday … 6=Saturday  (PostgreSQL EXTRACT(DOW) convention)
      - hour_bucket: EXTRACT(HOUR) // 4     (6 slots: 0=0-3h, 1=4-7h, …, 5=20-23h)
    """
    query = text("""
        SELECT
            EXTRACT(DOW  FROM transaction_date)::int          AS dow,
            (EXTRACT(HOUR FROM transaction_date)::int / 4)    AS hour_bucket,
            category,
            COUNT(*)                                          AS freq
        FROM transactions
        WHERE user_id        = :user_id
          AND transaction_date IS NOT NULL
          AND category         IS NOT NULL
        GROUP BY dow, hour_bucket, category
        ORDER BY dow, hour_bucket, freq DESC
    """)

    with get_session() as session:
        rows = session.execute(query, {"user_id": user_id}).fetchall()

    # For each slot keep the top-N distinct categories (rows already ordered by freq DESC)
    buckets: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        key = f"{int(row.dow)}_{int(row.hour_bucket)}"
        if len(buckets[key]) < TOP_N:
            buckets[key].append(row.category)

    return dict(buckets)


@app.task(bind=True, max_retries=3)
def compute_category_patterns(self):
    """Compute per-user category suggestions by day/hour slot; cache results in Redis."""
    r = _redis_client()
    processed = 0

    try:
        with get_session() as session:
            user_ids = [str(u.id) for u in session.query(User.id).all()]

        for user_id in user_ids:
            patterns = _compute_patterns_for_user(user_id)
            r.set(f"finflow:patterns:{user_id}", json.dumps(patterns), ex=CACHE_TTL)
            processed += 1

    except Exception as exc:
        logger.error("category_patterns failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)

    logger.info("category_patterns: processed %d users", processed)
    return {"processed": processed}
