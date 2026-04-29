import redis.asyncio as aioredis

from app.core.config import settings

# Redis DB allocation: 0=broker, 1=results, 2=pattern cache
_CACHE_DB = 2

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        base_url = settings.CELERY_BROKER_URL.rsplit("/", 1)[0]
        _client = aioredis.from_url(f"{base_url}/{_CACHE_DB}", decode_responses=True)
    return _client
