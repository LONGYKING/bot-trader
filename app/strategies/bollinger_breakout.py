"""
Bollinger Band breakout strategy.

Signal rules
------------
+7  Price closes above upper BB  AND  volume spike (volume > multiplier × avg)
+3  Price closes above upper BB  WITHOUT volume spike
-7  Price closes below lower BB  AND  volume spike
-3  Price closes below lower BB  WITHOUT volume spike
 0  Price within bands
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field

from app.core.indicators import add_bollinger
from app.strategies.base import BaseStrategy, SignalResult
from app.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Parameter model
# ---------------------------------------------------------------------------

class BollingerBreakoutParams(BaseModel):
    bb_period: int = Field(default=20, ge=5, le=200, description="Bollinger Band period")
    bb_std: float = Field(default=2.0, ge=0.5, le=5.0, description="Number of standard deviations")
    volume_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=10.0,
        description="Volume must exceed this multiple of the rolling average to qualify as a spike",
    )

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

@StrategyRegistry.register
class BollingerBreakoutStrategy(BaseStrategy):
    name = "bollinger_breakout"
    description = (
        "Generates CALL/PUT signals when price breaks outside Bollinger Bands. "
        "A volume spike upgrades the signal from weak (+3/-3) to strong (+7/-7)."
    )

    def validate_params(self, raw: dict) -> dict:
        return BollingerBreakoutParams(**raw).model_dump()

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df = add_bollinger(df, period=p["bb_period"], std=p["bb_std"])
        # Rolling average volume over bb_period bars
        if "volume" in df.columns:
            df = df.copy()
            df["volume_avg"] = df["volume"].rolling(p["bb_period"], min_periods=1).mean()
        return df

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if len(df) < self._warmup_bars():
            return SignalResult(signal_value=0, confidence=0.0, rule_triggered="warmup")

        p = self.params
        cur = df.iloc[-1]

        close = float(cur.get("close", 0) or 0)
        bb_upper = float(cur.get("bb_upper", 0) or 0)
        bb_lower = float(cur.get("bb_lower", 0) or 0)
        volume = float(cur.get("volume", 0) or 0)
        volume_avg = float(cur.get("volume_avg", 0) or 0)

        has_volume_spike = (
            volume_avg > 0 and volume > volume_avg * p["volume_multiplier"]
        )

        snapshot = {
            "close": round(close, 6),
            "bb_upper": round(bb_upper, 6),
            "bb_lower": round(bb_lower, 6),
            "volume": round(volume, 2),
            "volume_avg": round(volume_avg, 2),
            "has_volume_spike": has_volume_spike,
        }

        if bb_upper > 0 and close > bb_upper:
            if has_volume_spike:
                return SignalResult(
                    signal_value=7,
                    confidence=0.85,
                    indicator_snapshot=snapshot,
                    rule_triggered="bb_breakout_above_with_volume_spike",
                )
            return SignalResult(
                signal_value=3,
                confidence=0.55,
                indicator_snapshot=snapshot,
                rule_triggered="bb_breakout_above_no_volume_spike",
            )

        if bb_lower > 0 and close < bb_lower:
            if has_volume_spike:
                return SignalResult(
                    signal_value=-7,
                    confidence=0.85,
                    indicator_snapshot=snapshot,
                    rule_triggered="bb_breakout_below_with_volume_spike",
                )
            return SignalResult(
                signal_value=-3,
                confidence=0.55,
                indicator_snapshot=snapshot,
                rule_triggered="bb_breakout_below_no_volume_spike",
            )

        return SignalResult(
            signal_value=0,
            confidence=0.0,
            indicator_snapshot=snapshot,
            rule_triggered="price_within_bands",
        )

    def _warmup_bars(self) -> int:
        return self.params["bb_period"] + 25
