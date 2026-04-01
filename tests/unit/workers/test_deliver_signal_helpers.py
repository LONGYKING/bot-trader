"""Unit tests for deliver_signal helper functions.

Tests cover:
- _is_quiet_hour   — time window logic
- _is_rate_limited — Redis pipeline + counter logic
- _apply_notification_filters — channel-level signal filtering
- _apply_subscription_preferences — quiet hours + hourly throttle
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from freezegun import freeze_time

from app.types.channel_config import NotificationChannelConfig, _BaseChannelConfig
from app.types.subscription import QuietHours, SubscriptionPreferences
from app.workers.deliver_signal import (
    _apply_notification_filters,
    _apply_subscription_preferences,
    _is_quiet_hour,
    _is_rate_limited,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _delivery(channel_id: uuid.UUID | None = None, subscription_id: uuid.UUID | None = None):
    d = MagicMock()
    d.id = uuid.uuid4()
    d.channel_id = channel_id or uuid.uuid4()
    d.subscription_id = subscription_id or uuid.uuid4()
    return d


def _signal(signal_value: int = 7, trade_type: str = "options", direction: str = "call"):
    s = MagicMock()
    s.signal_value = signal_value
    s.trade_type = trade_type
    s.direction = direction
    return s


def _delivery_repo():
    repo = MagicMock()
    repo.mark_failed = AsyncMock(return_value=None)
    return repo


def _make_redis(pipeline_count: int = 1) -> MagicMock:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[pipeline_count, True])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


# ---------------------------------------------------------------------------
# _is_quiet_hour
# ---------------------------------------------------------------------------


class TestIsQuietHour:
    def test_no_quiet_hours_returns_false(self):
        prefs = SubscriptionPreferences()
        assert _is_quiet_hour(prefs) is False

    @freeze_time("2024-01-15 23:30:00", tz_offset=0)  # UTC 23:30
    def test_inside_overnight_window(self):
        prefs = SubscriptionPreferences(
            quiet_hours=QuietHours(start="22:00", end="08:00", timezone="UTC")
        )
        assert _is_quiet_hour(prefs) is True

    @freeze_time("2024-01-15 23:30:00", tz_offset=0)  # UTC 23:30
    def test_inside_non_overnight_window(self):
        prefs = SubscriptionPreferences(
            quiet_hours=QuietHours(start="22:00", end="23:59", timezone="UTC")
        )
        assert _is_quiet_hour(prefs) is True

    @freeze_time("2024-01-15 14:00:00", tz_offset=0)  # UTC 14:00
    def test_outside_quiet_window(self):
        prefs = SubscriptionPreferences(
            quiet_hours=QuietHours(start="22:00", end="08:00", timezone="UTC")
        )
        assert _is_quiet_hour(prefs) is False

    @freeze_time("2024-01-15 08:00:00", tz_offset=0)  # UTC 08:00 — boundary, end is exclusive
    def test_at_end_boundary_not_quiet(self):
        prefs = SubscriptionPreferences(
            quiet_hours=QuietHours(start="22:00", end="08:00", timezone="UTC")
        )
        assert _is_quiet_hour(prefs) is False

    @freeze_time("2024-01-15 22:00:00", tz_offset=0)  # UTC 22:00 — start boundary
    def test_at_start_boundary_is_quiet(self):
        prefs = SubscriptionPreferences(
            quiet_hours=QuietHours(start="22:00", end="08:00", timezone="UTC")
        )
        assert _is_quiet_hour(prefs) is True

    def test_invalid_timezone_returns_false(self):
        """Bad timezone must not raise — safe fallback."""
        prefs = SubscriptionPreferences(
            quiet_hours=QuietHours(start="22:00", end="08:00", timezone="Not/AReal_Timezone")
        )
        assert _is_quiet_hour(prefs) is False


# ---------------------------------------------------------------------------
# _is_rate_limited
# ---------------------------------------------------------------------------


class TestIsRateLimited:
    async def test_within_limit_returns_false(self):
        redis = _make_redis(pipeline_count=1)
        result = await _is_rate_limited(redis, uuid.uuid4(), limit=5)
        assert result is False

    async def test_at_limit_returns_false(self):
        # results[0] > limit, not >=. count=5, limit=5 → False
        redis = _make_redis(pipeline_count=5)
        result = await _is_rate_limited(redis, uuid.uuid4(), limit=5)
        assert result is False

    async def test_exceeds_limit_returns_true(self):
        redis = _make_redis(pipeline_count=6)
        result = await _is_rate_limited(redis, uuid.uuid4(), limit=5)
        assert result is True

    async def test_pipeline_used(self):
        """Verify both incr and expire are called atomically via pipeline."""
        redis = _make_redis(pipeline_count=1)
        pipe = redis.pipeline.return_value

        channel_id = uuid.uuid4()
        await _is_rate_limited(redis, channel_id, limit=10)

        redis.pipeline.assert_called_once()
        pipe.incr.assert_called_once()
        pipe.expire.assert_called_once()
        pipe.execute.assert_awaited_once()

    async def test_key_contains_channel_id(self):
        redis = _make_redis(pipeline_count=1)
        pipe = redis.pipeline.return_value

        channel_id = uuid.uuid4()
        await _is_rate_limited(redis, channel_id, limit=10)

        incr_key = pipe.incr.call_args[0][0]
        assert str(channel_id) in incr_key

    async def test_expire_set_to_60_seconds(self):
        redis = _make_redis(pipeline_count=1)
        pipe = redis.pipeline.return_value

        await _is_rate_limited(redis, uuid.uuid4(), limit=10)

        expire_args = pipe.expire.call_args[0]
        assert expire_args[1] == 60


# ---------------------------------------------------------------------------
# _apply_notification_filters
# ---------------------------------------------------------------------------


class TestApplyNotificationFilters:
    async def test_non_notification_config_passes(self):
        cfg = _BaseChannelConfig.model_validate({})
        result = await _apply_notification_filters(
            cfg, _signal(), _delivery(), _delivery_repo(), MagicMock()
        )
        assert result is False

    async def test_notifications_disabled_skips(self):
        cfg = NotificationChannelConfig(notifications_enabled=False)
        repo = _delivery_repo()
        delivery = _delivery()

        result = await _apply_notification_filters(cfg, _signal(), delivery, repo, MagicMock())

        assert result is True
        repo.mark_failed.assert_awaited_once()

    async def test_signal_below_min_strength_skips(self):
        cfg = NotificationChannelConfig(min_signal_strength=7)
        repo = _delivery_repo()

        signal = _signal(signal_value=3)  # abs(3) < 7
        result = await _apply_notification_filters(cfg, signal, _delivery(), repo, MagicMock())

        assert result is True
        repo.mark_failed.assert_awaited_once()

    async def test_signal_meets_min_strength_passes(self):
        cfg = NotificationChannelConfig(min_signal_strength=3)
        result = await _apply_notification_filters(
            cfg, _signal(signal_value=7), _delivery(), _delivery_repo(), MagicMock()
        )
        assert result is False

    async def test_trade_type_filtered(self):
        cfg = NotificationChannelConfig(trade_type_filter=["spot"])
        repo = _delivery_repo()

        signal = _signal(trade_type="options")
        result = await _apply_notification_filters(cfg, signal, _delivery(), repo, MagicMock())

        assert result is True

    async def test_trade_type_allowed(self):
        cfg = NotificationChannelConfig(trade_type_filter=["options", "futures"])
        result = await _apply_notification_filters(
            cfg, _signal(trade_type="options"), _delivery(), _delivery_repo(), MagicMock()
        )
        assert result is False

    async def test_direction_filter_long_only_blocks_short(self):
        cfg = NotificationChannelConfig(direction_filter="long_only")
        repo = _delivery_repo()

        signal = _signal(direction="put")  # short side
        result = await _apply_notification_filters(cfg, signal, _delivery(), repo, MagicMock())

        assert result is True

    async def test_direction_filter_long_only_passes_call(self):
        cfg = NotificationChannelConfig(direction_filter="long_only")

        signal = _signal(direction="long")
        result = await _apply_notification_filters(
            cfg, signal, _delivery(), _delivery_repo(), MagicMock()
        )
        assert result is False

    async def test_direction_filter_short_only_blocks_long(self):
        cfg = NotificationChannelConfig(direction_filter="short_only")
        repo = _delivery_repo()

        signal = _signal(direction="call")  # long side
        result = await _apply_notification_filters(cfg, signal, _delivery(), repo, MagicMock())

        assert result is True

    async def test_direction_filter_both_passes_all(self):
        cfg = NotificationChannelConfig(direction_filter="both")
        for direction in ("call", "put", "long", "short"):
            result = await _apply_notification_filters(
                cfg, _signal(direction=direction), _delivery(), _delivery_repo(), MagicMock()
            )
            assert result is False, f"Expected pass for direction={direction}"


# ---------------------------------------------------------------------------
# _apply_subscription_preferences
# ---------------------------------------------------------------------------


class TestApplySubscriptionPreferences:
    @freeze_time("2024-01-15 23:30:00", tz_offset=0)
    async def test_quiet_hours_skips_delivery(self):
        prefs = SubscriptionPreferences(
            quiet_hours=QuietHours(start="22:00", end="08:00", timezone="UTC")
        )
        repo = _delivery_repo()
        delivery = _delivery()

        result = await _apply_subscription_preferences(prefs, None, delivery, repo, MagicMock())

        assert result is True
        repo.mark_failed.assert_awaited_once()

    @freeze_time("2024-01-15 14:00:00", tz_offset=0)
    async def test_outside_quiet_hours_passes(self):
        prefs = SubscriptionPreferences(
            quiet_hours=QuietHours(start="22:00", end="08:00", timezone="UTC")
        )
        result = await _apply_subscription_preferences(
            prefs, None, _delivery(), _delivery_repo(), MagicMock()
        )
        assert result is False

    async def test_hourly_throttle_blocks_when_exceeded(self):
        prefs = SubscriptionPreferences(max_signals_per_hour=3)
        redis = _make_redis(pipeline_count=4)  # 4 > 3 → throttled
        repo = _delivery_repo()

        result = await _apply_subscription_preferences(
            prefs, redis, _delivery(), repo, MagicMock()
        )

        assert result is True
        repo.mark_failed.assert_awaited_once()

    async def test_hourly_throttle_passes_within_limit(self):
        prefs = SubscriptionPreferences(max_signals_per_hour=3)
        redis = _make_redis(pipeline_count=2)

        result = await _apply_subscription_preferences(
            prefs, redis, _delivery(), _delivery_repo(), MagicMock()
        )
        assert result is False

    async def test_hourly_throttle_uses_pipeline(self):
        prefs = SubscriptionPreferences(max_signals_per_hour=10)
        redis = _make_redis(pipeline_count=1)
        pipe = redis.pipeline.return_value

        await _apply_subscription_preferences(
            prefs, redis, _delivery(), _delivery_repo(), MagicMock()
        )

        redis.pipeline.assert_called_once()
        pipe.incr.assert_called_once()
        pipe.expire.assert_called_once()

    async def test_expire_set_to_3600(self):
        prefs = SubscriptionPreferences(max_signals_per_hour=10)
        redis = _make_redis(pipeline_count=1)
        pipe = redis.pipeline.return_value

        await _apply_subscription_preferences(
            prefs, redis, _delivery(), _delivery_repo(), MagicMock()
        )

        expire_args = pipe.expire.call_args[0]
        assert expire_args[1] == 3600

    async def test_no_redis_skips_throttle(self):
        """When redis is None, hourly throttle should be skipped."""
        prefs = SubscriptionPreferences(max_signals_per_hour=1)

        result = await _apply_subscription_preferences(
            prefs, None, _delivery(), _delivery_repo(), MagicMock()
        )
        assert result is False

    async def test_no_prefs_passes(self):
        prefs = SubscriptionPreferences()
        result = await _apply_subscription_preferences(
            prefs, None, _delivery(), _delivery_repo(), MagicMock()
        )
        assert result is False
