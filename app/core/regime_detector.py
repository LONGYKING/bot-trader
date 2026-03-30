"""
Algorithmic market regime classification.

Uses ADX for trend strength, +DI/-DI for direction, and ATR percentile rank
for volatility assessment.  Requires at minimum 30 bars of OHLCV data.
"""
from __future__ import annotations

from enum import Enum

import pandas as pd

from app.core.indicators import add_adx, add_atr


class Regime(str, Enum):
    STRONG_TREND_UP = "strong_trend_up"
    STRONG_TREND_DOWN = "strong_trend_down"
    WEAK_TREND_UP = "weak_trend_up"
    WEAK_TREND_DOWN = "weak_trend_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


def classify_regime(
    df: pd.DataFrame,
    adx_strong: float = 25.0,
    adx_weak: float = 20.0,
    atr_high_percentile: float = 75.0,
    atr_low_percentile: float = 25.0,
) -> str:
    """
    Classify the market regime for the latest bar in *df*.

    Parameters
    ----------
    df:
        OHLCV DataFrame.  Must have ``high``, ``low``, ``close`` columns and
        at least 30 rows.
    adx_strong:
        ADX threshold above which a trend is considered *strong* (default 25).
    adx_weak:
        ADX threshold above which a trend is considered *weak* (default 20).
    atr_high_percentile:
        Percentile rank of ATR above which volatility is classified as high
        (default 75).
    atr_low_percentile:
        Percentile rank of ATR below which volatility is classified as low
        (default 25).

    Returns
    -------
    str
        A :class:`Regime` enum value (as a string).

    Raises
    ------
    ValueError
        If *df* has fewer than 30 bars.
    """
    if len(df) < 30:
        raise ValueError(
            f"classify_regime requires at least 30 bars, got {len(df)}."
        )

    # Add ADX and ATR if not already present
    if "adx" not in df.columns or "dmp" not in df.columns or "dmn" not in df.columns:
        df = add_adx(df)
    if "atr" not in df.columns:
        df = add_atr(df)

    row = df.iloc[-1]
    adx = float(row.get("adx", 0) or 0)
    dmp = float(row.get("dmp", 0) or 0)  # +DI
    dmn = float(row.get("dmn", 0) or 0)  # -DI

    # ATR percentile rank over the full available window
    atr_series = df["atr"].dropna()
    if len(atr_series) > 1:
        atr_pct = float(atr_series.rank(pct=True).iloc[-1] * 100)
    else:
        atr_pct = 50.0

    # --- Classification priority ---
    # 1. High volatility (choppy, directionless but explosive)
    if atr_pct >= atr_high_percentile and adx < adx_weak:
        return Regime.HIGH_VOLATILITY

    # 2. Low volatility (quiet, compressed)
    if atr_pct <= atr_low_percentile and adx < adx_weak:
        return Regime.LOW_VOLATILITY

    # 3. Strong trend
    if adx >= adx_strong:
        if dmp > dmn:
            return Regime.STRONG_TREND_UP
        else:
            return Regime.STRONG_TREND_DOWN

    # 4. Weak trend
    if adx >= adx_weak:
        if dmp > dmn:
            return Regime.WEAK_TREND_UP
        else:
            return Regime.WEAK_TREND_DOWN

    # 5. Default: ranging / sideways
    return Regime.RANGING
