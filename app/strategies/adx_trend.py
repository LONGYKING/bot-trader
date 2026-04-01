"""
ADX Trend strategy.

Signal rules
------------
+7  ADX > adx_strong  AND  +DI > -DI  AND  RSI < 70 (not overbought)
-7  ADX > adx_strong  AND  -DI > +DI  AND  RSI > 30 (not oversold)
+3  adx_weak < ADX ≤ adx_strong  AND  +DI > -DI
-3  adx_weak < ADX ≤ adx_strong  AND  -DI > +DI
 0  ADX < adx_weak (no trend) or RSI guard prevents entry
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field

from app.core.indicators import add_adx, add_rsi
from app.strategies.base import BaseStrategy, SignalResult
from app.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Parameter model
# ---------------------------------------------------------------------------

class AdxTrendParams(BaseModel):
    adx_period: int = Field(default=14, ge=2, le=100, description="ADX look-back period")
    adx_strong: float = Field(
        default=25.0, ge=10.0, le=60.0, description="ADX threshold for a strong trend"
    )
    adx_weak: float = Field(
        default=20.0, ge=5.0, le=50.0, description="ADX threshold for a weak trend"
    )
    rsi_period: int = Field(default=14, ge=2, le=100, description="RSI look-back period")

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

@StrategyRegistry.register
class AdxTrendStrategy(BaseStrategy):
    name = "adx_trend"
    description = (
        "Uses ADX to measure trend strength and +DI/-DI for direction. "
        "RSI guards prevent entering strong-signal trades near overbought/oversold extremes."
    )

    def validate_params(self, raw: dict) -> dict:
        return AdxTrendParams(**raw).model_dump()

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df = add_adx(df, period=p["adx_period"])
        df = add_rsi(df, period=p["rsi_period"])
        return df

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if len(df) < self._warmup_bars():
            return SignalResult(signal_value=0, confidence=0.0, rule_triggered="warmup")

        p = self.params
        cur = df.iloc[-1]

        adx = float(cur.get("adx", 0) or 0)
        dmp = float(cur.get("dmp", 0) or 0)   # +DI
        dmn = float(cur.get("dmn", 0) or 0)   # -DI
        rsi = float(cur.get("rsi", 50) or 50)

        snapshot = {
            "adx": round(adx, 2),
            "dmp": round(dmp, 2),
            "dmn": round(dmn, 2),
            "rsi": round(rsi, 2),
        }

        if adx >= p["adx_strong"]:
            if dmp > dmn and rsi < 70:
                return SignalResult(
                    signal_value=7,
                    confidence=min(0.95, adx / 50.0),
                    indicator_snapshot=snapshot,
                    rule_triggered="adx_strong_bullish_rsi_ok",
                )
            if dmn > dmp and rsi > 30:
                return SignalResult(
                    signal_value=-7,
                    confidence=min(0.95, adx / 50.0),
                    indicator_snapshot=snapshot,
                    rule_triggered="adx_strong_bearish_rsi_ok",
                )

        if p["adx_weak"] <= adx < p["adx_strong"]:
            if dmp > dmn:
                return SignalResult(
                    signal_value=3,
                    confidence=min(0.65, adx / 50.0),
                    indicator_snapshot=snapshot,
                    rule_triggered="adx_weak_bullish",
                )
            if dmn > dmp:
                return SignalResult(
                    signal_value=-3,
                    confidence=min(0.65, adx / 50.0),
                    indicator_snapshot=snapshot,
                    rule_triggered="adx_weak_bearish",
                )

        return SignalResult(
            signal_value=0,
            confidence=0.0,
            indicator_snapshot=snapshot,
            rule_triggered="adx_below_threshold_or_rsi_guard",
        )

    def _warmup_bars(self) -> int:
        p = self.params
        return p["adx_period"] + p["rsi_period"] + 10
