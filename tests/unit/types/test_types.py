"""Unit tests for app/types domain models."""
import pytest
from pydantic import ValidationError

from app.types.channel_config import (
    EmailChannelConfig,
    ExchangeChannelConfig,
    NotificationChannelConfig,
    TelegramChannelConfig,
    _BaseChannelConfig,
    parse_channel_config,
)
from app.types.delivery import DeliveryMetadata
from app.types.signal import VALID_SIGNAL_VALUES, SignalData
from app.types.strategy import StrategyRiskConfig
from app.types.subscription import QuietHours, SubscriptionPreferences


# ---------------------------------------------------------------------------
# SignalData
# ---------------------------------------------------------------------------


class TestSignalData:
    def test_minimal_valid(self):
        s = SignalData(asset="BTC/USDT", signal_value=7)
        assert s.asset == "BTC/USDT"
        assert s.signal_value == 7
        assert s.trade_type == "options"
        assert s.indicator_snapshot == {}

    def test_full_fields(self):
        s = SignalData(
            asset="ETH/USDT",
            signal_value=-3,
            trade_type="futures",
            direction="short",
            tenor_days=3,
            confidence=0.85,
            regime="bearish",
            entry_price=3200.50,
            rule_triggered="macd_cross",
            indicator_snapshot={"rsi": 28.5, "macd": -1.2},
        )
        assert s.direction == "short"
        assert s.confidence == pytest.approx(0.85)
        assert s.indicator_snapshot["rsi"] == 28.5

    def test_extra_fields_ignored(self):
        # extra="ignore" — unknown keys should not raise
        s = SignalData(asset="BTC/USDT", signal_value=3, unknown_key="drop_me")
        assert not hasattr(s, "unknown_key")

    def test_valid_signal_values_frozenset(self):
        assert VALID_SIGNAL_VALUES == frozenset({-7, -3, 3, 7})
        assert 0 not in VALID_SIGNAL_VALUES


# ---------------------------------------------------------------------------
# StrategyRiskConfig
# ---------------------------------------------------------------------------


class TestStrategyRiskConfig:
    def test_empty_dict_uses_defaults(self):
        cfg = StrategyRiskConfig.model_validate({})
        assert cfg.min_confidence_threshold is None
        assert cfg.max_daily_signals is None
        assert cfg.cooldown_minutes is None
        assert cfg.suppress_duplicate_signals is False

    def test_valid_config(self):
        cfg = StrategyRiskConfig.model_validate(
            {"min_confidence_threshold": 0.7, "max_daily_signals": 5, "cooldown_minutes": 30}
        )
        assert cfg.min_confidence_threshold == 0.7
        assert cfg.max_daily_signals == 5
        assert cfg.cooldown_minutes == 30

    def test_cooldown_zero_rejected(self):
        with pytest.raises(ValidationError):
            StrategyRiskConfig(cooldown_minutes=0)

    def test_cooldown_negative_rejected(self):
        with pytest.raises(ValidationError):
            StrategyRiskConfig(cooldown_minutes=-5)

    def test_cooldown_positive_accepted(self):
        cfg = StrategyRiskConfig(cooldown_minutes=1)
        assert cfg.cooldown_minutes == 1

    def test_extra_keys_ignored(self):
        cfg = StrategyRiskConfig.model_validate({"legacy_field": "ignore_me"})
        assert not hasattr(cfg, "legacy_field")


# ---------------------------------------------------------------------------
# SubscriptionPreferences / QuietHours
# ---------------------------------------------------------------------------


class TestSubscriptionPreferences:
    def test_empty_prefs(self):
        prefs = SubscriptionPreferences.model_validate({})
        assert prefs.quiet_hours is None
        assert prefs.max_signals_per_hour is None
        assert prefs.delivery_delay_seconds == 0

    def test_quiet_hours_parsed(self):
        prefs = SubscriptionPreferences.model_validate(
            {"quiet_hours": {"start": "22:00", "end": "07:00", "timezone": "UTC"}}
        )
        assert prefs.quiet_hours is not None
        assert prefs.quiet_hours.start == "22:00"

    def test_max_signals_per_hour_ge1(self):
        with pytest.raises(ValidationError):
            SubscriptionPreferences(max_signals_per_hour=0)

    def test_delivery_delay_non_negative(self):
        with pytest.raises(ValidationError):
            SubscriptionPreferences(delivery_delay_seconds=-1)


class TestQuietHours:
    def test_valid_hhmm(self):
        qh = QuietHours(start="22:00", end="08:00")
        assert qh.timezone == "UTC"

    def test_invalid_format_rejected(self):
        with pytest.raises(ValidationError):
            QuietHours(start="2200", end="08:00")

    def test_invalid_hour_rejected(self):
        with pytest.raises(ValidationError):
            QuietHours(start="25:00", end="08:00")

    def test_invalid_minute_rejected(self):
        with pytest.raises(ValidationError):
            QuietHours(start="22:61", end="08:00")


# ---------------------------------------------------------------------------
# DeliveryMetadata
# ---------------------------------------------------------------------------


class TestDeliveryMetadata:
    def test_minimal(self):
        m = DeliveryMetadata(latency_ms=120, channel_type="telegram", formatter="TelegramFormatter")
        assert m.latency_ms == 120
        assert m.attempt == 1  # default

    def test_attempt_ge1(self):
        with pytest.raises(ValidationError):
            DeliveryMetadata(latency_ms=100, channel_type="slack", formatter="SlackFormatter", attempt=0)


# ---------------------------------------------------------------------------
# _BaseChannelConfig
# ---------------------------------------------------------------------------


class TestBaseChannelConfig:
    def test_defaults(self):
        cfg = _BaseChannelConfig.model_validate({})
        assert cfg.cb_failure_threshold is None
        assert cfg.max_retries is None
        assert cfg.rate_limit_per_minute is None

    def test_cb_failure_threshold_ge1(self):
        with pytest.raises(ValidationError):
            _BaseChannelConfig(cb_failure_threshold=0)

    def test_extra_keys_allowed(self):
        # extra="allow" on base — credentials pass through
        cfg = _BaseChannelConfig.model_validate({"bot_token": "abc123"})
        assert cfg.model_extra.get("bot_token") == "abc123"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# NotificationChannelConfig
# ---------------------------------------------------------------------------


class TestNotificationChannelConfig:
    def test_defaults(self):
        cfg = NotificationChannelConfig.model_validate({})
        assert cfg.notifications_enabled is True
        assert cfg.direction_filter == "both"

    def test_invalid_direction_filter(self):
        with pytest.raises(ValidationError):
            NotificationChannelConfig(direction_filter="sideways")

    def test_valid_direction_filters(self):
        for val in ("both", "long_only", "short_only"):
            cfg = NotificationChannelConfig(direction_filter=val)
            assert cfg.direction_filter == val


# ---------------------------------------------------------------------------
# TelegramChannelConfig
# ---------------------------------------------------------------------------


class TestTelegramChannelConfig:
    def test_valid(self):
        cfg = TelegramChannelConfig(bot_token="tok:123", chat_id="-1001234567890")
        assert cfg.bot_token == "tok:123"

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            TelegramChannelConfig.model_validate({})


# ---------------------------------------------------------------------------
# EmailChannelConfig
# ---------------------------------------------------------------------------


class TestEmailChannelConfig:
    def test_valid(self):
        cfg = EmailChannelConfig(
            username="user@example.com",
            password="secret",
            from_address="from@example.com",
            to_addresses=["to@example.com"],
        )
        assert cfg.smtp_host == "smtp.gmail.com"
        assert cfg.smtp_port == 587
        assert cfg.use_tls is True

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            EmailChannelConfig.model_validate({})


# ---------------------------------------------------------------------------
# ExchangeChannelConfig
# ---------------------------------------------------------------------------


class TestExchangeChannelConfig:
    def _valid_dict(self):
        return {
            "exchange_id": "binance",
            "api_key": "key123",
            "api_secret": "secret456",
        }

    def test_valid_defaults(self):
        cfg = ExchangeChannelConfig.model_validate(self._valid_dict())
        assert cfg.position_size_pct == pytest.approx(0.05)
        assert cfg.leverage == 1
        assert cfg.order_type == "market"
        assert cfg.trading_enabled is True
        assert cfg.dry_run is False

    def test_missing_credentials_raises(self):
        with pytest.raises(ValidationError):
            ExchangeChannelConfig.model_validate({"exchange_id": "binance"})

    def test_invalid_order_type(self):
        with pytest.raises(ValidationError):
            ExchangeChannelConfig.model_validate({**self._valid_dict(), "order_type": "iceberg"})

    def test_invalid_direction_filter(self):
        with pytest.raises(ValidationError):
            ExchangeChannelConfig.model_validate(
                {**self._valid_dict(), "direction_filter": "neutral"}
            )

    def test_position_size_pct_bounds(self):
        with pytest.raises(ValidationError):
            ExchangeChannelConfig.model_validate({**self._valid_dict(), "position_size_pct": 1.5})


# ---------------------------------------------------------------------------
# parse_channel_config
# ---------------------------------------------------------------------------


class TestParseChannelConfig:
    def test_telegram(self):
        cfg = parse_channel_config("telegram", {"bot_token": "tok", "chat_id": "123"})
        assert isinstance(cfg, TelegramChannelConfig)

    def test_exchange(self):
        cfg = parse_channel_config(
            "exchange",
            {"exchange_id": "bybit", "api_key": "k", "api_secret": "s"},
        )
        assert isinstance(cfg, ExchangeChannelConfig)

    def test_unknown_type_falls_back_to_base(self):
        cfg = parse_channel_config("fax_machine", {})
        assert isinstance(cfg, _BaseChannelConfig)
