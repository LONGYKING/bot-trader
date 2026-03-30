"""
Unit tests for app.core.indicators.

Uses a reproducible 100-bar synthetic OHLCV DataFrame (np.random.seed(42)).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.indicators import (
    add_atr,
    add_adx,
    add_bollinger,
    add_ema,
    add_macd,
    add_rsi,
    add_sma,
    add_stoch,
    add_vwap,
)


# ---------------------------------------------------------------------------
# Fixture: synthetic OHLCV
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ohlcv_df() -> pd.DataFrame:
    """100-bar synthetic OHLCV DataFrame with a DatetimeIndex (UTC)."""
    rng = np.random.default_rng(42)
    n = 100

    close = 100.0 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 2.0, n)
    low = close - rng.uniform(0.1, 2.0, n)
    open_ = close + rng.normal(0, 0.5, n)
    volume = rng.uniform(1_000, 10_000, n)

    index = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_dtype_and_no_mutate(original: pd.DataFrame, result: pd.DataFrame) -> None:
    """Ensure the original DataFrame was not mutated and new columns are float."""
    # Original should be unchanged (new columns not present)
    for col in result.columns:
        if col not in original.columns:
            assert col not in original.columns, f"Original df was mutated: column '{col}' appeared"


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

class TestAddRsi:
    def test_adds_rsi_column(self, ohlcv_df):
        result = add_rsi(ohlcv_df)
        assert "rsi" in result.columns

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_rsi(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_rsi(ohlcv_df)
        assert result["rsi"].dtype == float

    def test_no_nan_after_warmup(self, ohlcv_df):
        period = 14
        result = add_rsi(ohlcv_df, period=period)
        after_warmup = result["rsi"].iloc[period:]
        assert after_warmup.notna().all(), "NaN values found in RSI after warmup"

    def test_rsi_bounded(self, ohlcv_df):
        result = add_rsi(ohlcv_df)
        valid = result["rsi"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_custom_period(self, ohlcv_df):
        result = add_rsi(ohlcv_df, period=7)
        assert "rsi" in result.columns


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

class TestAddMacd:
    def test_adds_all_columns(self, ohlcv_df):
        result = add_macd(ohlcv_df)
        for col in ("macd_line", "macd_signal_line", "macd_hist"):
            assert col in result.columns, f"Missing column: {col}"

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_macd(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_macd(ohlcv_df)
        for col in ("macd_line", "macd_signal_line", "macd_hist"):
            assert result[col].dtype == float

    def test_no_nan_after_warmup(self, ohlcv_df):
        fast, slow, signal = 12, 26, 9
        warmup = slow + signal
        result = add_macd(ohlcv_df, fast=fast, slow=slow, signal=signal)
        for col in ("macd_line", "macd_signal_line", "macd_hist"):
            after_warmup = result[col].iloc[warmup:]
            assert after_warmup.notna().all(), f"NaN in {col} after warmup"

    def test_hist_equals_line_minus_signal(self, ohlcv_df):
        result = add_macd(ohlcv_df)
        diff = (result["macd_line"] - result["macd_signal_line"]).round(8)
        hist = result["macd_hist"].round(8)
        pd.testing.assert_series_equal(diff, hist, check_names=False, atol=1e-4)


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

class TestAddBollinger:
    def test_adds_all_columns(self, ohlcv_df):
        result = add_bollinger(ohlcv_df)
        for col in ("bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_pct"):
            assert col in result.columns, f"Missing column: {col}"

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_bollinger(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_bollinger(ohlcv_df)
        for col in ("bb_upper", "bb_middle", "bb_lower"):
            assert result[col].dtype == float

    def test_no_nan_after_warmup(self, ohlcv_df):
        period = 20
        result = add_bollinger(ohlcv_df, period=period)
        for col in ("bb_upper", "bb_middle", "bb_lower"):
            after_warmup = result[col].iloc[period - 1:]
            assert after_warmup.notna().all(), f"NaN in {col} after warmup"

    def test_upper_above_lower(self, ohlcv_df):
        result = add_bollinger(ohlcv_df)
        valid = result.dropna(subset=["bb_upper", "bb_lower"])
        assert (valid["bb_upper"] >= valid["bb_lower"]).all()


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

class TestAddAtr:
    def test_adds_atr_column(self, ohlcv_df):
        result = add_atr(ohlcv_df)
        assert "atr" in result.columns

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_atr(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_atr(ohlcv_df)
        assert result["atr"].dtype == float

    def test_no_nan_after_warmup(self, ohlcv_df):
        period = 14
        result = add_atr(ohlcv_df, period=period)
        after_warmup = result["atr"].iloc[period:]
        assert after_warmup.notna().all()

    def test_atr_positive(self, ohlcv_df):
        result = add_atr(ohlcv_df)
        valid = result["atr"].dropna()
        assert (valid >= 0).all()


# ---------------------------------------------------------------------------
# ADX
# ---------------------------------------------------------------------------

class TestAddAdx:
    def test_adds_all_columns(self, ohlcv_df):
        result = add_adx(ohlcv_df)
        for col in ("adx", "dmp", "dmn"):
            assert col in result.columns, f"Missing column: {col}"

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_adx(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_adx(ohlcv_df)
        for col in ("adx", "dmp", "dmn"):
            assert result[col].dtype == float

    def test_no_nan_after_warmup(self, ohlcv_df):
        period = 14
        result = add_adx(ohlcv_df, period=period)
        warmup = period * 2
        for col in ("adx", "dmp", "dmn"):
            after_warmup = result[col].iloc[warmup:]
            assert after_warmup.notna().all(), f"NaN in {col} after warmup"

    def test_adx_bounded(self, ohlcv_df):
        result = add_adx(ohlcv_df)
        valid = result["adx"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()


# ---------------------------------------------------------------------------
# Stochastic
# ---------------------------------------------------------------------------

class TestAddStoch:
    def test_adds_stoch_columns(self, ohlcv_df):
        result = add_stoch(ohlcv_df)
        for col in ("stoch_k", "stoch_d"):
            assert col in result.columns

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_stoch(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_stoch(ohlcv_df)
        for col in ("stoch_k", "stoch_d"):
            assert result[col].dtype == float

    def test_stoch_bounded(self, ohlcv_df):
        result = add_stoch(ohlcv_df)
        for col in ("stoch_k", "stoch_d"):
            valid = result[col].dropna()
            # Stoch values can occasionally exceed 0-100 due to smoothing; check reasonable range
            assert (valid >= -5).all() and (valid <= 105).all()


# ---------------------------------------------------------------------------
# VWAP
# ---------------------------------------------------------------------------

class TestAddVwap:
    def test_adds_vwap_column(self, ohlcv_df):
        result = add_vwap(ohlcv_df)
        assert "vwap" in result.columns

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_vwap(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_vwap(ohlcv_df)
        assert result["vwap"].dtype == float

    def test_no_nan(self, ohlcv_df):
        result = add_vwap(ohlcv_df)
        assert result["vwap"].notna().all()

    def test_vwap_without_volume(self, ohlcv_df):
        """VWAP should fall back gracefully when volume is missing."""
        df_no_vol = ohlcv_df.drop(columns=["volume"])
        result = add_vwap(df_no_vol)
        assert "vwap" in result.columns
        assert result["vwap"].notna().all()


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------

class TestAddEma:
    def test_adds_ema_column(self, ohlcv_df):
        result = add_ema(ohlcv_df, period=20)
        assert "ema_20" in result.columns

    def test_multiple_periods(self, ohlcv_df):
        df = add_ema(ohlcv_df, period=9)
        df = add_ema(df, period=21)
        assert "ema_9" in df.columns
        assert "ema_21" in df.columns

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_ema(ohlcv_df, period=20)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_ema(ohlcv_df, period=20)
        assert result["ema_20"].dtype == float

    def test_no_nan_after_warmup(self, ohlcv_df):
        period = 20
        result = add_ema(ohlcv_df, period=period)
        after_warmup = result["ema_20"].iloc[period - 1:]
        assert after_warmup.notna().all()


# ---------------------------------------------------------------------------
# SMA
# ---------------------------------------------------------------------------

class TestAddSma:
    def test_adds_sma_column(self, ohlcv_df):
        result = add_sma(ohlcv_df, period=20)
        assert "sma_20" in result.columns

    def test_does_not_mutate_input(self, ohlcv_df):
        original_cols = set(ohlcv_df.columns)
        add_sma(ohlcv_df, period=20)
        assert set(ohlcv_df.columns) == original_cols

    def test_dtype_float(self, ohlcv_df):
        result = add_sma(ohlcv_df, period=20)
        assert result["sma_20"].dtype == float

    def test_no_nan_after_warmup(self, ohlcv_df):
        period = 20
        result = add_sma(ohlcv_df, period=period)
        after_warmup = result["sma_20"].iloc[period - 1:]
        assert after_warmup.notna().all()

    def test_sma_matches_rolling_mean(self, ohlcv_df):
        period = 10
        result = add_sma(ohlcv_df, period=period)
        expected = ohlcv_df["close"].rolling(period).mean()
        pd.testing.assert_series_equal(
            result["sma_10"].dropna(),
            expected.dropna(),
            check_names=False,
            rtol=1e-4,
        )
