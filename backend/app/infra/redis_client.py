from functools import cache

import redis.asyncio as redis_async

from app.config import get_settings


@cache
def get_redis() -> redis_async.Redis:
    return redis_async.from_url(get_settings().redis_url, decode_responses=True)
