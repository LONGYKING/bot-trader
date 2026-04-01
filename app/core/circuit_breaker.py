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

from app.config import get_settings


class CircuitBreaker:
    def __init__(
        self,
        redis: Any,
        channel_id: str,
        failure_threshold: int | None = None,
        recovery_timeout: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        s = get_settings()
        self.redis = redis
        self.channel_id = channel_id
        self.failure_threshold = failure_threshold or s.circuit_breaker_failure_threshold
        self.recovery_timeout = recovery_timeout or s.circuit_breaker_recovery_timeout_seconds
        self.window_sec = window_seconds or s.circuit_breaker_window_seconds
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
        pipe.expire(self._failure_key, self.window_sec)
        results = await pipe.execute()
        count = results[0]
        if count >= self.failure_threshold:
            await self.redis.setex(self._open_key, self.recovery_timeout, "1")

    async def record_success(self) -> None:
        """Reset failure counter and close circuit."""
        await self.redis.delete(self._failure_key, self._open_key)

    async def get_state(self) -> str:
        is_open = await self.redis.exists(self._open_key)
        return "OPEN" if is_open else "CLOSED"
