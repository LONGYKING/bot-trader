"""
Redis-backed circuit breaker for delivery channels.
States: CLOSED (normal), OPEN (failing, block calls), HALF_OPEN (testing recovery).

Config per channel:
- failure_threshold: 5 failures in window
- recovery_timeout: 300 seconds (5 min) before trying again
- window: 60 seconds

Usage:
    cb = CircuitBreaker(redis, channel_id="abc-123")
    if await cb.is_open():
        raise ExternalServiceError("Channel circuit breaker OPEN")
    try:
        result = await channel.send(msg)
        await cb.record_success()
    except Exception:
        await cb.record_failure()
        raise
"""
from typing import Any

FAILURE_THRESHOLD = 5
RECOVERY_TIMEOUT = 300   # seconds
WINDOW_SEC = 60


class CircuitBreaker:
    def __init__(self, redis: Any, channel_id: str) -> None:
        self.redis = redis
        self.channel_id = channel_id
        self._failure_key = f"cb:failures:{channel_id}"
        self._open_key = f"cb:open:{channel_id}"

    async def is_open(self) -> bool:
        """Returns True if circuit is OPEN (calls should be blocked)."""
        is_open = await self.redis.exists(self._open_key)
        return bool(is_open)

    async def record_failure(self) -> None:
        """Increment failure counter. Open circuit if threshold exceeded."""
        pipe = self.redis.pipeline()
        pipe.incr(self._failure_key)
        pipe.expire(self._failure_key, WINDOW_SEC)
        results = await pipe.execute()
        count = results[0]
        if count >= FAILURE_THRESHOLD:
            await self.redis.setex(self._open_key, RECOVERY_TIMEOUT, "1")

    async def record_success(self) -> None:
        """Reset failure counter and close circuit."""
        await self.redis.delete(self._failure_key, self._open_key)

    async def get_state(self) -> str:
        is_open = await self.redis.exists(self._open_key)
        return "OPEN" if is_open else "CLOSED"
