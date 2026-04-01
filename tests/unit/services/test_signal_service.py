"""Unit tests for signal_service pure helpers.

Tests cover:
- VALID_SIGNAL_VALUES constant
- _resolve_direction_and_tenor — direction/tenor derivation
- _build_signal_dict — signal dict construction
- force_signal validation — invalid signal_value raises ValueError
"""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import NotFoundError
from app.services.signal_service import _build_signal_dict, _resolve_direction_and_tenor
from app.types.signal import VALID_SIGNAL_VALUES


# ---------------------------------------------------------------------------
# VALID_SIGNAL_VALUES
# ---------------------------------------------------------------------------


class TestValidSignalValues:
    def test_contains_expected_values(self):
        assert VALID_SIGNAL_VALUES == frozenset({-7, -3, 3, 7})

    def test_zero_not_valid(self):
        assert 0 not in VALID_SIGNAL_VALUES

    def test_is_frozenset(self):
        assert isinstance(VALID_SIGNAL_VALUES, frozenset)


# ---------------------------------------------------------------------------
# _resolve_direction_and_tenor
# ---------------------------------------------------------------------------


class TestResolveDirectionAndTenor:
    # --- Options ---

    def test_options_positive_strong_gives_call_7days(self):
        direction, tenor_days, expiry_time = _resolve_direction_and_tenor("options", 7)
        assert direction == "call"
        assert tenor_days == 7
        assert expiry_time is not None

    def test_options_negative_strong_gives_put_7days(self):
        direction, tenor_days, expiry_time = _resolve_direction_and_tenor("options", -7)
        assert direction == "put"
        assert tenor_days == 7

    def test_options_positive_weak_gives_call_3days(self):
        direction, tenor_days, expiry_time = _resolve_direction_and_tenor("options", 3)
        assert direction == "call"
        assert tenor_days == 3

    def test_options_negative_weak_gives_put_3days(self):
        direction, tenor_days, expiry_time = _resolve_direction_and_tenor("options", -3)
        assert direction == "put"
        assert tenor_days == 3

    def test_options_expiry_approximately_now_plus_tenor(self):
        before = datetime.now(UTC)
        direction, tenor_days, expiry_time = _resolve_direction_and_tenor("options", 7)
        after = datetime.now(UTC)

        assert expiry_time is not None
        expected_lo = before + timedelta(days=7)
        expected_hi = after + timedelta(days=7)
        assert expected_lo <= expiry_time <= expected_hi

    # --- Spot ---

    def test_spot_positive_gives_long_no_tenor(self):
        direction, tenor_days, expiry_time = _resolve_direction_and_tenor("spot", 7)
        assert direction == "long"
        assert tenor_days is None
        assert expiry_time is None

    def test_spot_negative_gives_short_no_tenor(self):
        direction, tenor_days, expiry_time = _resolve_direction_and_tenor("spot", -3)
        assert direction == "short"
        assert tenor_days is None

    # --- Futures ---

    def test_futures_positive_gives_long(self):
        direction, tenor_days, _ = _resolve_direction_and_tenor("futures", 3)
        assert direction == "long"
        assert tenor_days is None

    def test_futures_negative_gives_short(self):
        direction, tenor_days, _ = _resolve_direction_and_tenor("futures", -7)
        assert direction == "short"
        assert tenor_days is None


# ---------------------------------------------------------------------------
# _build_signal_dict
# ---------------------------------------------------------------------------


class TestBuildSignalDict:
    def _default_kwargs(self, **overrides):
        base = dict(
            strategy_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            asset="BTC/USDT",
            timeframe="1h",
            signal_value=7,
            trade_type="options",
            confidence=0.9,
            regime="trending",
            entry_price=50000.0,
            indicator_snapshot={"rsi": 72.1},
            rule_triggered="rsi_overbought",
        )
        base.update(overrides)
        return base

    def test_required_keys_present(self):
        d = _build_signal_dict(**self._default_kwargs())
        required = {
            "strategy_id", "asset", "timeframe", "signal_value", "trade_type",
            "direction", "tenor_days", "confidence", "regime", "entry_price",
            "entry_time", "expiry_time", "indicator_snapshot", "rule_triggered", "created_at",
        }
        assert required.issubset(d.keys())

    def test_options_strong_buy_direction_and_tenor(self):
        d = _build_signal_dict(**self._default_kwargs(signal_value=7, trade_type="options"))
        assert d["direction"] == "call"
        assert d["tenor_days"] == 7
        assert d["expiry_time"] is not None

    def test_options_weak_sell_direction_and_tenor(self):
        d = _build_signal_dict(**self._default_kwargs(signal_value=-3, trade_type="options"))
        assert d["direction"] == "put"
        assert d["tenor_days"] == 3

    def test_spot_long_no_tenor(self):
        d = _build_signal_dict(**self._default_kwargs(signal_value=3, trade_type="spot"))
        assert d["direction"] == "long"
        assert d["tenor_days"] is None
        assert d["expiry_time"] is None

    def test_entry_time_and_created_at_are_utc_aware(self):
        d = _build_signal_dict(**self._default_kwargs())
        assert d["entry_time"].tzinfo is not None
        assert d["created_at"].tzinfo is not None

    def test_passthrough_fields_preserved(self):
        strategy_id = uuid.uuid4()
        d = _build_signal_dict(
            **self._default_kwargs(
                strategy_id=strategy_id,
                asset="ETH/USDT",
                timeframe="4h",
                confidence=0.75,
                regime="ranging",
                indicator_snapshot={"macd": 0.5},
                rule_triggered="macd_bull",
            )
        )
        assert d["strategy_id"] == strategy_id
        assert d["asset"] == "ETH/USDT"
        assert d["timeframe"] == "4h"
        assert d["confidence"] == pytest.approx(0.75)
        assert d["regime"] == "ranging"
        assert d["indicator_snapshot"] == {"macd": 0.5}
        assert d["rule_triggered"] == "macd_bull"


# ---------------------------------------------------------------------------
# force_signal — invalid signal_value
# ---------------------------------------------------------------------------


class TestForceSignalValidation:
    async def test_invalid_signal_value_raises_value_error(self):
        from app.services.signal_service import force_signal

        session = MagicMock()
        arq_pool = MagicMock()

        with pytest.raises(ValueError, match="signal_value must be one of"):
            await force_signal(session, arq_pool, uuid.uuid4(), signal_value=5)

    async def test_zero_signal_value_raises(self):
        from app.services.signal_service import force_signal

        session = MagicMock()
        arq_pool = MagicMock()

        with pytest.raises(ValueError):
            await force_signal(session, arq_pool, uuid.uuid4(), signal_value=0)

    @pytest.mark.parametrize("valid_value", [-7, -3, 3, 7])
    async def test_valid_signal_values_proceed_past_validation(self, valid_value):
        """Valid values should not raise on the validation check.

        We patch strategy_repo to raise NotFoundError so we don't need a real
        DB session, but confirm the ValueError is NOT raised first.
        """
        from app.services.signal_service import force_signal

        session = MagicMock()
        arq_pool = MagicMock()

        mock_strategy_repo = MagicMock()
        mock_strategy_repo.get_by_id = AsyncMock(return_value=None)

        with patch("app.services.signal_service.StrategyRepository", return_value=mock_strategy_repo):
            with pytest.raises(NotFoundError):
                await force_signal(session, arq_pool, uuid.uuid4(), signal_value=valid_value)
