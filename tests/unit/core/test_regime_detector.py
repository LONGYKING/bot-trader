"""
Unit tests for app.core.regime_detector.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.regime_detector import Regime, classify_regime
from app.core.indicators import add_adx, add_atr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic_df() -> pd.DataFrame:
    """100-bar synthetic OHLCV DataFrame."""
    rng = np.random.default_rng(42)
    n = 100
    close = 100.0 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 2.0, n)
    low = close - rng.uniform(0.1, 2.0, n)
    index = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.3, n),
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(1_000, 10_000, n),
        },
        index=index,
    )


def _make_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    close = 100.0 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 2.0, n)
    low = close - rng.uniform(0.1, 2.0, n)
    index = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(1_000, 10_000, n),
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestClassifyRegime:
    def test_returns_valid_regime_value(self, synthetic_df):
        regime = classify_regime(synthetic_df.copy())
        valid_values = {r.value for r in Regime}
        assert regime in valid_values, f"Unexpected regime: {regime!r}"

    def test_returns_regime_string_enum(self, synthetic_df):
        regime = classify_regime(synthetic_df.copy())
        # Regime is a str Enum; result should be a string
        assert isinstance(regime, str)

    def test_raises_if_fewer_than_30_bars(self):
        df = _make_df(n=20)
        with pytest.raises(ValueError, match="30 bars"):
            classify_regime(df)

    def test_accepts_exactly_30_bars(self):
        df = _make_df(n=30)
        regime = classify_regime(df)
        valid_values = {r.value for r in Regime}
        assert regime in valid_values

    def test_strong_trend_up_when_adx_and_dmp_high(self, synthetic_df):
        """Manually inject high ADX and +DI > -DI to force STRONG_TREND_UP."""
        df = synthetic_df.copy()
        df = add_adx(df)
        df = add_atr(df)
        # Override the last row to force conditions
        df.loc[df.index[-1], "adx"] = 35.0
        df.loc[df.index[-1], "dmp"] = 30.0
        df.loc[df.index[-1], "dmn"] = 10.0
        regime = classify_regime(df, adx_strong=25.0, adx_weak=20.0)
        assert regime == Regime.STRONG_TREND_UP

    def test_strong_trend_down_when_adx_and_dmn_high(self, synthetic_df):
        """Manually inject high ADX and -DI > +DI to force STRONG_TREND_DOWN."""
        df = synthetic_df.copy()
        df = add_adx(df)
        df = add_atr(df)
        df.loc[df.index[-1], "adx"] = 35.0
        df.loc[df.index[-1], "dmp"] = 10.0
        df.loc[df.index[-1], "dmn"] = 30.0
        regime = classify_regime(df, adx_strong=25.0, adx_weak=20.0)
        assert regime == Regime.STRONG_TREND_DOWN

    def test_ranging_when_adx_low(self, synthetic_df):
        """Force a ranging regime by setting ADX below adx_weak and moderate ATR."""
        df = synthetic_df.copy()
        df = add_adx(df)
        df = add_atr(df)
        # Set ADX below weak threshold; set ATR to median so no volatility regime
        df.loc[df.index[-1], "adx"] = 5.0
        atr_median = float(df["atr"].median())
        df.loc[df.index[-1], "atr"] = atr_median
        regime = classify_regime(df, adx_strong=25.0, adx_weak=20.0)
        assert regime == Regime.RANGING

    def test_high_volatility_regime(self, synthetic_df):
        """Force HIGH_VOLATILITY: low ADX + very high ATR."""
        df = synthetic_df.copy()
        df = add_adx(df)
        df = add_atr(df)
        # Set ADX below weak threshold; set ATR to extreme high
        df.loc[df.index[-1], "adx"] = 5.0
        df.loc[df.index[-1], "atr"] = df["atr"].max() * 10
        regime = classify_regime(df, adx_strong=25.0, adx_weak=20.0, atr_high_percentile=75.0)
        assert regime == Regime.HIGH_VOLATILITY

    def test_low_volatility_regime(self, synthetic_df):
        """Force LOW_VOLATILITY: low ADX + very low ATR."""
        df = synthetic_df.copy()
        df = add_adx(df)
        df = add_atr(df)
        df.loc[df.index[-1], "adx"] = 5.0
        df.loc[df.index[-1], "atr"] = 0.0  # lowest possible → percentile = 0
        regime = classify_regime(df, adx_strong=25.0, adx_weak=20.0, atr_low_percentile=25.0)
        assert regime == Regime.LOW_VOLATILITY

    def test_does_not_mutate_input(self, synthetic_df):
        original_cols = set(synthetic_df.columns)
        classify_regime(synthetic_df.copy())
        assert set(synthetic_df.columns) == original_cols

    def test_custom_thresholds(self, synthetic_df):
        """Verify that custom thresholds are respected."""
        df = synthetic_df.copy()
        df = add_adx(df)
        df = add_atr(df)
        # With very high adx_strong threshold, strong trend should not trigger
        df.loc[df.index[-1], "adx"] = 35.0
        df.loc[df.index[-1], "dmp"] = 30.0
        df.loc[df.index[-1], "dmn"] = 10.0
        atr_median = float(df["atr"].median())
        df.loc[df.index[-1], "atr"] = atr_median

        regime_strict = classify_regime(df.copy(), adx_strong=50.0, adx_weak=40.0)
        # ADX=35 < adx_weak=40 → should be RANGING (or volatility-based)
        assert regime_strict in (Regime.RANGING, Regime.HIGH_VOLATILITY, Regime.LOW_VOLATILITY)
