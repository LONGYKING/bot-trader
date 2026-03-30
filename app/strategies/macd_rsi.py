"""
MACD + RSI combined strategy.

Signal rules
------------
+7  MACD line crosses above signal line AND RSI < 60 AND MACD histogram > 0 (strong momentum)
+3  MACD line crosses above signal line AND RSI < 70 (moderate momentum)
-7  MACD line crosses below signal line AND RSI > 40 AND MACD histogram < 0
-3  MACD line crosses below signal line AND RSI > 30
 0  No crossover or RSI at extremes (overbought/oversold trap)
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from app.strategies.base import BaseStrategy, SignalResult
from app.strategies.registry import StrategyRegistry
from app.core.indicators import add_macd, add_rsi


# ---------------------------------------------------------------------------
# Parameter model
# ---------------------------------------------------------------------------

class MacdRsiParams(BaseModel):
    macd_fast: int = Field(default=12, ge=2, le=50, description="MACD fast EMA period")
    macd_slow: int = Field(default=26, ge=5, le=200, description="MACD slow EMA period")
    macd_signal: int = Field(default=9, ge=2, le=50, description="MACD signal line period")
    rsi_period: int = Field(default=14, ge=2, le=100, description="RSI look-back period")
    rsi_overbought: float = Field(default=70.0, ge=50.0, le=100.0, description="RSI overbought threshold")
    rsi_oversold: float = Field(default=30.0, ge=0.0, le=50.0, description="RSI oversold threshold")

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def fast_must_be_less_than_slow(self) -> "MacdRsiParams":
        if self.macd_fast >= self.macd_slow:
            raise ValueError(
                f"macd_fast ({self.macd_fast}) must be less than macd_slow ({self.macd_slow})"
            )
        return self


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

@StrategyRegistry.register
class MacdRsiStrategy(BaseStrategy):
    name = "macd_rsi"
    description = (
        "Generates CALL/PUT signals based on MACD crossovers filtered by RSI "
        "to avoid entries in overbought/oversold conditions."
    )

    def validate_params(self, raw: dict) -> dict:
        return MacdRsiParams(**raw).model_dump()

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df = add_macd(df, fast=p["macd_fast"], slow=p["macd_slow"], signal=p["macd_signal"])
        df = add_rsi(df, period=p["rsi_period"])
        return df

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if len(df) < 2:
            return SignalResult(signal_value=0, confidence=0.0, rule_triggered="insufficient_data")

        p = self.params
        cur = df.iloc[-1]
        prev = df.iloc[-2]

        macd_line = float(cur.get("macd_line", 0) or 0)
        macd_sig = float(cur.get("macd_signal_line", 0) or 0)
        macd_hist = float(cur.get("macd_hist", 0) or 0)
        prev_macd = float(prev.get("macd_line", 0) or 0)
        prev_sig = float(prev.get("macd_signal_line", 0) or 0)
        rsi = float(cur.get("rsi", 50) or 50)

        bullish_cross = prev_macd <= prev_sig and macd_line > macd_sig
        bearish_cross = prev_macd >= prev_sig and macd_line < macd_sig

        snapshot = {
            "macd_line": round(macd_line, 6),
            "macd_signal_line": round(macd_sig, 6),
            "macd_hist": round(macd_hist, 6),
            "rsi": round(rsi, 2),
        }

        if bullish_cross:
            if rsi < p["rsi_overbought"] - 10 and macd_hist > 0:
                return SignalResult(
                    signal_value=7,
                    confidence=min(0.9, (p["rsi_overbought"] - rsi) / 70.0),
                    indicator_snapshot=snapshot,
                    rule_triggered="macd_bullish_cross_rsi_low_hist_positive",
                )
            if rsi < p["rsi_overbought"]:
                return SignalResult(
                    signal_value=3,
                    confidence=min(0.65, (p["rsi_overbought"] - rsi) / 100.0),
                    indicator_snapshot=snapshot,
                    rule_triggered="macd_bullish_cross_rsi_ok",
                )

        if bearish_cross:
            if rsi > p["rsi_oversold"] + 10 and macd_hist < 0:
                return SignalResult(
                    signal_value=-7,
                    confidence=min(0.9, (rsi - p["rsi_oversold"]) / 70.0),
                    indicator_snapshot=snapshot,
                    rule_triggered="macd_bearish_cross_rsi_high_hist_negative",
                )
            if rsi > p["rsi_oversold"]:
                return SignalResult(
                    signal_value=-3,
                    confidence=min(0.65, (rsi - p["rsi_oversold"]) / 100.0),
                    indicator_snapshot=snapshot,
                    rule_triggered="macd_bearish_cross_rsi_ok",
                )

        return SignalResult(signal_value=0, confidence=0.0, indicator_snapshot=snapshot, rule_triggered="no_signal")

    def _warmup_bars(self) -> int:
        p = self.params
        return p["macd_slow"] + p["macd_signal"] + p["rsi_period"] + 10
