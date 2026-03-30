"""
Unit tests for all 6 built-in strategy implementations.

Each strategy is tested with a 200-bar synthetic OHLCV DataFrame to verify:
  - compute_indicators adds expected columns without error
  - generate_signal returns a SignalResult with a valid signal_value
  - generate_signal_series returns a pd.Series of the same length as df
  - validate_params({}) succeeds and uses defaults
  - validate_params with an unknown key raises an error
"""
from __future__ import annotations

from typing import Type

import numpy as np
import pandas as pd
import pytest
import pydantic

import app.strategies  # noqa: F401 — triggers registration

from app.strategies.base import BaseStrategy, SignalResult
from app.strategies.macd_rsi import MacdRsiStrategy
from app.strategies.bollinger_breakout import BollingerBreakoutStrategy
from app.strategies.rsi_divergence import RsiDivergenceStrategy
from app.strategies.ema_crossover import EmaCrossoverStrategy
from app.strategies.adx_trend import AdxTrendStrategy
from app.strategies.vwap_reversion import VwapReversionStrategy

VALID_SIGNAL_VALUES = {-7, -3, 0, 3, 7}


# ---------------------------------------------------------------------------
# Synthetic data fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ohlcv_200() -> pd.DataFrame:
    """200-bar synthetic OHLCV DataFrame (reproducible)."""
    rng = np.random.default_rng(42)
    n = 200
    close = 100.0 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 2.0, n)
    low = close - rng.uniform(0.1, 2.0, n)
    open_ = close + rng.normal(0, 0.3, n)
    volume = rng.uniform(1_000, 10_000, n)
    index = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _check_signal_result(result: SignalResult) -> None:
    assert isinstance(result, SignalResult)
    assert result.signal_value in VALID_SIGNAL_VALUES, (
        f"Invalid signal_value: {result.signal_value}"
    )
    assert 0.0 <= result.confidence <= 1.0, f"Confidence out of range: {result.confidence}"


def _check_signal_series(series: pd.Series, df: pd.DataFrame) -> None:
    assert isinstance(series, pd.Series)
    assert len(series) == len(df), (
        f"Signal series length {len(series)} != df length {len(df)}"
    )
    invalid = set(series.unique()) - VALID_SIGNAL_VALUES
    assert not invalid, f"Invalid signal values in series: {invalid}"


# ---------------------------------------------------------------------------
# Parametrized strategy tests
# ---------------------------------------------------------------------------

STRATEGY_CLASSES: list[Type[BaseStrategy]] = [
    MacdRsiStrategy,
    BollingerBreakoutStrategy,
    RsiDivergenceStrategy,
    EmaCrossoverStrategy,
    AdxTrendStrategy,
    VwapReversionStrategy,
]


@pytest.mark.parametrize("strategy_cls", STRATEGY_CLASSES, ids=lambda c: c.name)
class TestStrategyInterface:
    def test_validate_params_defaults(self, strategy_cls: Type[BaseStrategy]):
        """validate_params({}) should succeed and produce a valid params dict."""
        instance = strategy_cls({})
        assert isinstance(instance.params, dict)

    def test_validate_params_invalid_key_raises(self, strategy_cls: Type[BaseStrategy]):
        """Providing an unknown param key should raise a validation error."""
        with pytest.raises((ValueError, pydantic.ValidationError)):
            strategy_cls({"__nonexistent_key__": 999})

    def test_compute_indicators_returns_dataframe(
        self, strategy_cls: Type[BaseStrategy], ohlcv_200: pd.DataFrame
    ):
        instance = strategy_cls({})
        result = instance.compute_indicators(ohlcv_200)
        assert isinstance(result, pd.DataFrame)

    def test_compute_indicators_adds_columns(
        self, strategy_cls: Type[BaseStrategy], ohlcv_200: pd.DataFrame
    ):
        instance = strategy_cls({})
        result = instance.compute_indicators(ohlcv_200)
        assert len(result.columns) > len(ohlcv_200.columns), (
            f"{strategy_cls.name}: compute_indicators did not add any columns"
        )

    def test_compute_indicators_does_not_mutate_input(
        self, strategy_cls: Type[BaseStrategy], ohlcv_200: pd.DataFrame
    ):
        original_cols = set(ohlcv_200.columns)
        instance = strategy_cls({})
        instance.compute_indicators(ohlcv_200)
        assert set(ohlcv_200.columns) == original_cols

    def test_generate_signal_returns_valid_signal_result(
        self, strategy_cls: Type[BaseStrategy], ohlcv_200: pd.DataFrame
    ):
        instance = strategy_cls({})
        enriched = instance.compute_indicators(ohlcv_200)
        result = instance.generate_signal(enriched)
        _check_signal_result(result)

    def test_generate_signal_series_correct_length(
        self, strategy_cls: Type[BaseStrategy], ohlcv_200: pd.DataFrame
    ):
        instance = strategy_cls({})
        series = instance.generate_signal_series(ohlcv_200)
        _check_signal_series(series, ohlcv_200)

    def test_generate_signal_series_valid_values(
        self, strategy_cls: Type[BaseStrategy], ohlcv_200: pd.DataFrame
    ):
        instance = strategy_cls({})
        series = instance.generate_signal_series(ohlcv_200)
        invalid = set(series.unique()) - VALID_SIGNAL_VALUES
        assert not invalid, (
            f"{strategy_cls.name}: invalid signal values in series: {invalid}"
        )

    def test_generate_signal_series_same_index_as_df(
        self, strategy_cls: Type[BaseStrategy], ohlcv_200: pd.DataFrame
    ):
        instance = strategy_cls({})
        series = instance.generate_signal_series(ohlcv_200)
        pd.testing.assert_index_equal(series.index, ohlcv_200.index)

    def test_warmup_bars_is_positive_int(self, strategy_cls: Type[BaseStrategy]):
        instance = strategy_cls({})
        warmup = instance._warmup_bars()
        assert isinstance(warmup, int) and warmup > 0


# ---------------------------------------------------------------------------
# Strategy-specific parameter validation tests
# ---------------------------------------------------------------------------

class TestMacdRsiParams:
    def test_fast_must_be_less_than_slow(self):
        with pytest.raises((ValueError, pydantic.ValidationError)):
            MacdRsiStrategy({"macd_fast": 30, "macd_slow": 12})

    def test_valid_custom_params(self):
        instance = MacdRsiStrategy({"macd_fast": 8, "macd_slow": 21, "rsi_period": 10})
        assert instance.params["macd_fast"] == 8
        assert instance.params["macd_slow"] == 21

    def test_rsi_period_out_of_range(self):
        with pytest.raises((ValueError, pydantic.ValidationError)):
            MacdRsiStrategy({"rsi_period": 1})


class TestBollingerBreakoutParams:
    def test_valid_custom_params(self):
        instance = BollingerBreakoutStrategy({"bb_period": 30, "bb_std": 1.5})
        assert instance.params["bb_period"] == 30

    def test_volume_multiplier_min(self):
        # volume_multiplier < 1.0 should fail (ge=1.0)
        with pytest.raises((ValueError, pydantic.ValidationError)):
            BollingerBreakoutStrategy({"volume_multiplier": 0.5})


class TestRsiDivergenceParams:
    def test_valid_custom_params(self):
        instance = RsiDivergenceStrategy({"rsi_period": 21, "lookback": 15})
        assert instance.params["lookback"] == 15

    def test_lookback_min(self):
        with pytest.raises((ValueError, pydantic.ValidationError)):
            RsiDivergenceStrategy({"lookback": 1})


class TestEmaCrossoverParams:
    def test_periods_must_be_ascending(self):
        with pytest.raises((ValueError, pydantic.ValidationError)):
            EmaCrossoverStrategy({"fast_period": 20, "slow_period": 10, "signal_period": 50})

    def test_slow_must_be_less_than_signal(self):
        with pytest.raises((ValueError, pydantic.ValidationError)):
            EmaCrossoverStrategy({"fast_period": 9, "slow_period": 60, "signal_period": 50})

    def test_valid_custom_params(self):
        instance = EmaCrossoverStrategy({"fast_period": 5, "slow_period": 13, "signal_period": 50})
        assert instance.params["fast_period"] == 5


class TestAdxTrendParams:
    def test_valid_custom_params(self):
        instance = AdxTrendStrategy({"adx_strong": 30.0, "adx_weak": 22.0})
        assert instance.params["adx_strong"] == 30.0


class TestVwapReversionParams:
    def test_valid_custom_params(self):
        instance = VwapReversionStrategy({"rsi_oversold": 30.0, "rsi_overbought": 70.0})
        assert instance.params["rsi_oversold"] == 30.0

    def test_deviation_min(self):
        with pytest.raises((ValueError, pydantic.ValidationError)):
            VwapReversionStrategy({"vwap_deviation_pct": 0.0})
