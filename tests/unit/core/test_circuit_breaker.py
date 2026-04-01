"""Unit tests for the Redis-backed CircuitBreaker."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.circuit_breaker import CircuitBreaker


def _make_redis(exists_result: int = 0) -> MagicMock:
    """Return a mock Redis client with an async pipeline."""
    redis = MagicMock()
    redis.exists = AsyncMock(return_value=exists_result)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)

    pipe = MagicMock()
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True])
    redis.pipeline = MagicMock(return_value=pipe)

    return redis


@pytest.fixture
def settings_patch():
    """Patch get_settings to return predictable values."""
    mock_settings = MagicMock()
    mock_settings.circuit_breaker_failure_threshold = 5
    mock_settings.circuit_breaker_recovery_timeout_seconds = 300
    mock_settings.circuit_breaker_window_seconds = 60
    with patch("app.core.circuit_breaker.get_settings", return_value=mock_settings):
        yield mock_settings


class TestCircuitBreakerInit:
    def test_uses_settings_defaults(self, settings_patch):
        redis = _make_redis()
        cb = CircuitBreaker(redis, "chan-1")
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 300
        assert cb.window_sec == 60
        assert cb._failure_key == "cb:failures:chan-1"
        assert cb._open_key == "cb:open:chan-1"

    def test_overrides_take_precedence(self, settings_patch):
        redis = _make_redis()
        cb = CircuitBreaker(redis, "chan-2", failure_threshold=3, recovery_timeout=60, window_seconds=30)
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 60
        assert cb.window_sec == 30


class TestIsOpen:
    async def test_closed_when_key_absent(self, settings_patch):
        redis = _make_redis(exists_result=0)
        cb = CircuitBreaker(redis, "chan-1")
        assert await cb.is_open() is False
        redis.exists.assert_awaited_once_with("cb:open:chan-1")

    async def test_open_when_key_present(self, settings_patch):
        redis = _make_redis(exists_result=1)
        cb = CircuitBreaker(redis, "chan-1")
        assert await cb.is_open() is True


class TestGetState:
    async def test_closed_state(self, settings_patch):
        redis = _make_redis(exists_result=0)
        cb = CircuitBreaker(redis, "chan-1")
        assert await cb.get_state() == "CLOSED"

    async def test_open_state(self, settings_patch):
        redis = _make_redis(exists_result=1)
        cb = CircuitBreaker(redis, "chan-1")
        assert await cb.get_state() == "OPEN"


class TestRecordSuccess:
    async def test_deletes_both_keys(self, settings_patch):
        redis = _make_redis()
        cb = CircuitBreaker(redis, "chan-1")
        await cb.record_success()
        redis.delete.assert_awaited_once_with("cb:failures:chan-1", "cb:open:chan-1")


class TestRecordFailure:
    async def test_pipeline_commands_issued(self, settings_patch):
        redis = _make_redis()
        pipe = redis.pipeline.return_value
        pipe.execute = AsyncMock(return_value=[1, True])

        cb = CircuitBreaker(redis, "chan-1")
        await cb.record_failure()

        redis.pipeline.assert_called_once()
        pipe.incr.assert_called_once_with("cb:failures:chan-1")
        pipe.expire.assert_called_once_with("cb:failures:chan-1", cb.window_sec)
        pipe.execute.assert_awaited_once()

    async def test_does_not_open_below_threshold(self, settings_patch):
        redis = _make_redis()
        pipe = redis.pipeline.return_value
        # count = 4, threshold = 5 → no open
        pipe.execute = AsyncMock(return_value=[4, True])

        cb = CircuitBreaker(redis, "chan-1")
        await cb.record_failure()

        redis.setex.assert_not_awaited()

    async def test_opens_circuit_at_threshold(self, settings_patch):
        redis = _make_redis()
        pipe = redis.pipeline.return_value
        pipe.execute = AsyncMock(return_value=[5, True])  # exactly at threshold

        cb = CircuitBreaker(redis, "chan-1")
        await cb.record_failure()

        redis.setex.assert_awaited_once_with("cb:open:chan-1", cb.recovery_timeout, "1")

    async def test_opens_circuit_above_threshold(self, settings_patch):
        redis = _make_redis()
        pipe = redis.pipeline.return_value
        pipe.execute = AsyncMock(return_value=[10, True])

        cb = CircuitBreaker(redis, "chan-1")
        await cb.record_failure()

        redis.setex.assert_awaited_once()

    async def test_custom_failure_threshold(self, settings_patch):
        redis = _make_redis()
        pipe = redis.pipeline.return_value
        pipe.execute = AsyncMock(return_value=[3, True])

        cb = CircuitBreaker(redis, "chan-1", failure_threshold=3)
        await cb.record_failure()

        redis.setex.assert_awaited_once()

    async def test_recovery_timeout_used_in_setex(self, settings_patch):
        redis = _make_redis()
        pipe = redis.pipeline.return_value
        pipe.execute = AsyncMock(return_value=[5, True])

        cb = CircuitBreaker(redis, "chan-1", recovery_timeout=120)
        await cb.record_failure()

        redis.setex.assert_awaited_once_with("cb:open:chan-1", 120, "1")
