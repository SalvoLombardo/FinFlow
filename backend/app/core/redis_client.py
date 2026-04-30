from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.core.config import settings

# Redis DB allocation: 0=broker, 1=results, 2=pattern cache + rate limits
_CACHE_DB = 2

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        base_url = settings.CELERY_BROKER_URL.rsplit("/", 1)[0]
        _client = aioredis.from_url(f"{base_url}/{_CACHE_DB}", decode_responses=True)
    return _client


async def check_ai_rate_limit(user_id: str) -> bool:
    """Increment daily AI request counter. Returns True if allowed (count <= limit)."""
    client = get_redis()
    key = f"finflow:ai_rate:{user_id}"
    count = await client.incr(key)
    if count == 1:
        now = datetime.now(timezone.utc)
        end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=timezone.utc)
        ttl = max(1, int((end_of_day - now).total_seconds()) + 1)
        await client.expire(key, ttl)
    return count <= settings.AI_DAILY_RATE_LIMIT
