import redis.asyncio as redis_async
from app.config import get_settings

_pool: redis_async.Redis | None = None


def get_redis() -> redis_async.Redis:
    global _pool
    if _pool is None:
        _pool = redis_async.from_url(get_settings().redis_url, decode_responses=True)
    return _pool
