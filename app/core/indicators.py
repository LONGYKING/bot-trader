"""
Thin pandas-ta wrapper helpers.

Each function accepts a DataFrame, adds one or more columns to a *copy* of
that DataFrame, and returns it.  The caller's DataFrame is never mutated.

All functions are intentionally lightweight: they delegate the heavy lifting
to ``pandas_ta`` and only add a stable, readable column-name interface on top.
"""
from __future__ import annotations

import pandas as pd

try:
    import pandas_ta as ta  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pandas_ta is required for indicator calculations. "
        "Install it with: pip install pandas_ta"
    ) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_copy(df: pd.DataFrame) -> pd.DataFrame:
    """Return a shallow copy so we never mutate the caller's DataFrame."""
    return df.copy()


def _safe_series(series: pd.Series | None, index: pd.Index, fill: float = 0.0) -> pd.Series:
    """Return *series* aligned to *index*, filling NaN with *fill*."""
    if series is None:
        return pd.Series(fill, index=index, dtype=float)
    return series.reindex(index).fillna(fill)


# ---------------------------------------------------------------------------
# Public indicator functions
# ---------------------------------------------------------------------------

def add_rsi(df: pd.DataFrame, period: int = 14, col: str = "close") -> pd.DataFrame:
    """
    Add ``rsi`` column to *df*.

    Parameters
    ----------
    period:
        RSI look-back window (default 14).
    col:
        Source price column (default ``"close"``).
    """
    df = _ensure_copy(df)
    result = ta.rsi(df[col], length=period)
    df["rsi"] = _safe_series(result, df.index)
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    col: str = "close",
) -> pd.DataFrame:
    """
    Add ``macd_line``, ``macd_signal_line``, ``macd_hist`` columns.

    Parameters
    ----------
    fast:
        Fast EMA period (default 12).
    slow:
        Slow EMA period (default 26).
    signal:
        Signal line period (default 9).
    col:
        Source price column (default ``"close"``).
    """
    df = _ensure_copy(df)
    result = ta.macd(df[col], fast=fast, slow=slow, signal=signal)
    if result is not None and not result.empty:
        # pandas_ta MACD column names: MACD_{fast}_{slow}_{signal},
        #   MACDs_{fast}_{slow}_{signal}, MACDh_{fast}_{slow}_{signal}
        cols = result.columns.tolist()
        macd_col = next((c for c in cols if c.startswith("MACD_")), None)
        sig_col = next((c for c in cols if c.startswith("MACDs_")), None)
        hist_col = next((c for c in cols if c.startswith("MACDh_")), None)
        df["macd_line"] = _safe_series(result[macd_col] if macd_col else None, df.index)
        df["macd_signal_line"] = _safe_series(result[sig_col] if sig_col else None, df.index)
        df["macd_hist"] = _safe_series(result[hist_col] if hist_col else None, df.index)
    else:
        df["macd_line"] = 0.0
        df["macd_signal_line"] = 0.0
        df["macd_hist"] = 0.0
    return df


def add_bollinger(
    df: pd.DataFrame,
    period: int = 20,
    std: float = 2.0,
    col: str = "close",
) -> pd.DataFrame:
    """
    Add Bollinger Band columns:
    ``bb_upper``, ``bb_middle``, ``bb_lower``, ``bb_width``, ``bb_pct``.

    Parameters
    ----------
    period:
        Rolling window for the middle band (default 20).
    std:
        Number of standard deviations for the bands (default 2.0).
    col:
        Source price column (default ``"close"``).
    """
    df = _ensure_copy(df)
    result = ta.bbands(df[col], length=period, std=std)
    if result is not None and not result.empty:
        cols = result.columns.tolist()
        upper_col = next((c for c in cols if "BBU" in c), None)
        mid_col = next((c for c in cols if "BBM" in c), None)
        lower_col = next((c for c in cols if "BBL" in c), None)
        bw_col = next((c for c in cols if "BBB" in c), None)
        pct_col = next((c for c in cols if "BBP" in c), None)
        df["bb_upper"] = _safe_series(result[upper_col] if upper_col else None, df.index)
        df["bb_middle"] = _safe_series(result[mid_col] if mid_col else None, df.index)
        df["bb_lower"] = _safe_series(result[lower_col] if lower_col else None, df.index)
        df["bb_width"] = _safe_series(result[bw_col] if bw_col else None, df.index)
        df["bb_pct"] = _safe_series(result[pct_col] if pct_col else None, df.index)
    else:
        for col_name in ("bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_pct"):
            df[col_name] = 0.0
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add ``atr`` column (Average True Range).

    Parameters
    ----------
    period:
        ATR look-back window (default 14).
    """
    df = _ensure_copy(df)
    result = ta.atr(df["high"], df["low"], df["close"], length=period)
    df["atr"] = _safe_series(result, df.index)
    return df


def add_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Add ``adx``, ``dmp`` (+DI), ``dmn`` (-DI) columns.

    Parameters
    ----------
    period:
        ADX look-back window (default 14).
    """
    df = _ensure_copy(df)
    result = ta.adx(df["high"], df["low"], df["close"], length=period)
    if result is not None and not result.empty:
        cols = result.columns.tolist()
        adx_col = next((c for c in cols if c.startswith("ADX_")), None)
        dmp_col = next((c for c in cols if c.startswith("DMP_")), None)
        dmn_col = next((c for c in cols if c.startswith("DMN_")), None)
        df["adx"] = _safe_series(result[adx_col] if adx_col else None, df.index)
        df["dmp"] = _safe_series(result[dmp_col] if dmp_col else None, df.index)
        df["dmn"] = _safe_series(result[dmn_col] if dmn_col else None, df.index)
    else:
        df["adx"] = 0.0
        df["dmp"] = 0.0
        df["dmn"] = 0.0
    return df


def add_stoch(
    df: pd.DataFrame,
    k: int = 14,
    d: int = 3,
    smooth_k: int = 3,
) -> pd.DataFrame:
    """
    Add ``stoch_k`` and ``stoch_d`` columns (Stochastic Oscillator).

    Parameters
    ----------
    k:
        %K period (default 14).
    d:
        %D smoothing period (default 3).
    smooth_k:
        %K additional smoothing (default 3).
    """
    df = _ensure_copy(df)
    result = ta.stoch(df["high"], df["low"], df["close"], k=k, d=d, smooth_k=smooth_k)
    if result is not None and not result.empty:
        cols = result.columns.tolist()
        stoch_k_col = next((c for c in cols if c.startswith("STOCHk_")), None)
        stoch_d_col = next((c for c in cols if c.startswith("STOCHd_")), None)
        df["stoch_k"] = _safe_series(result[stoch_k_col] if stoch_k_col else None, df.index)
        df["stoch_d"] = _safe_series(result[stoch_d_col] if stoch_d_col else None, df.index)
    else:
        df["stoch_k"] = 0.0
        df["stoch_d"] = 0.0
    return df


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ``vwap`` column (Volume-Weighted Average Price).

    Uses pandas_ta.vwap when available.  Falls back to a manual cumulative
    calculation if the DataFrame has no ``volume`` column or if pandas_ta
    returns None.

    Note: pandas_ta's VWAP resets each session (trading day) by default when
    a DatetimeIndex with timezone info is present.
    """
    df = _ensure_copy(df)
    has_volume = "volume" in df.columns and df["volume"].notna().any()

    if has_volume:
        try:
            result = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
            if result is not None and not result.empty:
                df["vwap"] = _safe_series(result, df.index, fill=float("nan"))
                # Fill remaining NaN with the close price as a fallback
                df["vwap"] = df["vwap"].fillna(df["close"])
                return df
        except Exception:
            pass  # fall through to manual calculation

    # Manual cumulative VWAP (session-agnostic, intraday only approximation)
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    if has_volume:
        volume = df["volume"]
        df["vwap"] = (typical_price * volume).cumsum() / volume.cumsum()
    else:
        # No volume: use simple cumulative average of typical price
        df["vwap"] = typical_price.expanding().mean()

    return df


def add_ema(df: pd.DataFrame, period: int, col: str = "close") -> pd.DataFrame:
    """
    Add ``ema_{period}`` column (Exponential Moving Average).

    Parameters
    ----------
    period:
        EMA period.
    col:
        Source price column (default ``"close"``).
    """
    df = _ensure_copy(df)
    result = ta.ema(df[col], length=period)
    df[f"ema_{period}"] = _safe_series(result, df.index)
    return df


def add_sma(df: pd.DataFrame, period: int, col: str = "close") -> pd.DataFrame:
    """
    Add ``sma_{period}`` column (Simple Moving Average).

    Parameters
    ----------
    period:
        SMA period.
    col:
        Source price column (default ``"close"``).
    """
    df = _ensure_copy(df)
    result = ta.sma(df[col], length=period)
    df[f"sma_{period}"] = _safe_series(result, df.index)
    return df
