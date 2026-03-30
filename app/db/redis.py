import redis.asyncio as aioredis
from arq import ArqRedis
from arq.connections import RedisSettings, create_pool

from app.config import get_settings

_redis_pool = None
_arq_pool: ArqRedis | None = None


async def get_redis() -> aioredis.Redis:
    """Returns a plain Redis client (for rate-limiting, caching, etc.)."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis_dsn,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def get_arq_pool() -> ArqRedis:
    """Returns the arq Redis pool used for enqueue_job calls."""
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(get_arq_redis_settings())
    return _arq_pool


async def close_redis() -> None:
    global _redis_pool, _arq_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None


def get_arq_redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings.from_dsn(settings.redis_dsn)
