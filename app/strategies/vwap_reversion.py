"""
VWAP Mean Reversion strategy.

Signal rules
------------
+7  price < VWAP × (1 - vwap_deviation_pct)  AND  RSI < rsi_oversold
+3  price < VWAP × (1 - vwap_deviation_pct/2)  AND  RSI < 45
-7  price > VWAP × (1 + vwap_deviation_pct)  AND  RSI > rsi_overbought
-3  price > VWAP × (1 + vwap_deviation_pct/2)  AND  RSI > 55
 0  price near VWAP

Note: VWAP is computed by pandas_ta which resets each trading day when the
      DataFrame has a tz-aware DatetimeIndex.
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field

from app.strategies.base import BaseStrategy, SignalResult
from app.strategies.registry import StrategyRegistry
from app.core.indicators import add_rsi, add_vwap


# ---------------------------------------------------------------------------
# Parameter model
# ---------------------------------------------------------------------------

class VwapReversionParams(BaseModel):
    vwap_deviation_pct: float = Field(
        default=0.02,
        ge=0.001,
        le=0.20,
        description="Minimum price deviation from VWAP (as a fraction) to trigger a signal",
    )
    rsi_period: int = Field(default=14, ge=2, le=100, description="RSI look-back period")
    rsi_oversold: float = Field(
        default=35.0, ge=10.0, le=50.0, description="RSI level considered oversold"
    )
    rsi_overbought: float = Field(
        default=65.0, ge=50.0, le=90.0, description="RSI level considered overbought"
    )

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

@StrategyRegistry.register
class VwapReversionStrategy(BaseStrategy):
    name = "vwap_reversion"
    description = (
        "Mean-reversion strategy that buys when price is significantly below VWAP "
        "and RSI is oversold, and sells when price is significantly above VWAP with "
        "an overbought RSI. VWAP resets each trading day."
    )

    def validate_params(self, raw: dict) -> dict:
        return VwapReversionParams(**raw).model_dump()

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df = add_vwap(df)
        df = add_rsi(df, period=p["rsi_period"])
        return df

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if len(df) < self._warmup_bars():
            return SignalResult(signal_value=0, confidence=0.0, rule_triggered="warmup")

        p = self.params
        cur = df.iloc[-1]

        close = float(cur.get("close", 0) or 0)
        vwap = float(cur.get("vwap", 0) or 0)
        rsi = float(cur.get("rsi", 50) or 50)

        if vwap == 0:
            return SignalResult(signal_value=0, confidence=0.0, rule_triggered="vwap_unavailable")

        dev = p["vwap_deviation_pct"]
        half_dev = dev / 2.0

        lower_strong = vwap * (1.0 - dev)
        lower_mild = vwap * (1.0 - half_dev)
        upper_strong = vwap * (1.0 + dev)
        upper_mild = vwap * (1.0 + half_dev)

        snapshot = {
            "close": round(close, 6),
            "vwap": round(vwap, 6),
            "rsi": round(rsi, 2),
            "lower_strong": round(lower_strong, 6),
            "upper_strong": round(upper_strong, 6),
        }

        # --- Bullish (buy) signals ---
        if close < lower_strong and rsi < p["rsi_oversold"]:
            return SignalResult(
                signal_value=7,
                confidence=min(0.90, (p["rsi_oversold"] - rsi) / p["rsi_oversold"] + 0.5),
                indicator_snapshot=snapshot,
                rule_triggered="vwap_strong_buy_oversold",
            )
        if close < lower_mild and rsi < 45:
            return SignalResult(
                signal_value=3,
                confidence=0.55,
                indicator_snapshot=snapshot,
                rule_triggered="vwap_mild_buy",
            )

        # --- Bearish (sell) signals ---
        if close > upper_strong and rsi > p["rsi_overbought"]:
            return SignalResult(
                signal_value=-7,
                confidence=min(0.90, (rsi - p["rsi_overbought"]) / (100 - p["rsi_overbought"]) + 0.5),
                indicator_snapshot=snapshot,
                rule_triggered="vwap_strong_sell_overbought",
            )
        if close > upper_mild and rsi > 55:
            return SignalResult(
                signal_value=-3,
                confidence=0.55,
                indicator_snapshot=snapshot,
                rule_triggered="vwap_mild_sell",
            )

        return SignalResult(
            signal_value=0,
            confidence=0.0,
            indicator_snapshot=snapshot,
            rule_triggered="price_near_vwap",
        )

    def _warmup_bars(self) -> int:
        return self.params["rsi_period"] + 20
