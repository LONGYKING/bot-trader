"""
EMA Crossover strategy with trend filter.

Signal rules
------------
+7  Fast EMA crosses above slow EMA  AND  price > signal EMA (trend confirmation)
+3  Fast EMA crosses above slow EMA  (no trend confirmation)
-7  Fast EMA crosses below slow EMA  AND  price < signal EMA
-3  Fast EMA crosses below slow EMA  (no trend confirmation)
 0  No crossover
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from app.core.indicators import add_ema
from app.strategies.base import BaseStrategy, SignalResult
from app.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Parameter model
# ---------------------------------------------------------------------------

class EmaCrossoverParams(BaseModel):
    fast_period: int = Field(default=9, ge=2, le=100, description="Fast EMA period")
    slow_period: int = Field(default=21, ge=5, le=200, description="Slow EMA period")
    signal_period: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Trend-filter EMA period (long-term direction)",
    )

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def periods_must_be_ascending(self) -> EmaCrossoverParams:
        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"fast_period ({self.fast_period}) must be less than slow_period ({self.slow_period})"
            )
        if self.slow_period >= self.signal_period:
            raise ValueError(
                f"slow_period ({self.slow_period}) must be less than signal_period ({self.signal_period})"
            )
        return self


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

@StrategyRegistry.register
class EmaCrossoverStrategy(BaseStrategy):
    name = "ema_crossover"
    description = (
        "Generates CALL/PUT signals on EMA crossovers, with the long-term signal EMA "
        "used as a trend filter to distinguish strong (+7/-7) from weak (+3/-3) signals."
    )

    def validate_params(self, raw: dict) -> dict:
        return EmaCrossoverParams(**raw).model_dump()

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df = add_ema(df, period=p["fast_period"])
        df = add_ema(df, period=p["slow_period"])
        df = add_ema(df, period=p["signal_period"])
        return df

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        if len(df) < 2:
            return SignalResult(signal_value=0, confidence=0.0, rule_triggered="insufficient_data")

        p = self.params
        fast_col = f"ema_{p['fast_period']}"
        slow_col = f"ema_{p['slow_period']}"
        signal_col = f"ema_{p['signal_period']}"

        cur = df.iloc[-1]
        prev = df.iloc[-2]

        fast_cur = float(cur.get(fast_col, 0) or 0)
        slow_cur = float(cur.get(slow_col, 0) or 0)
        fast_prev = float(prev.get(fast_col, 0) or 0)
        slow_prev = float(prev.get(slow_col, 0) or 0)
        signal_ema = float(cur.get(signal_col, 0) or 0)
        close = float(cur.get("close", 0) or 0)

        # Crossover detection
        bullish_cross = fast_prev <= slow_prev and fast_cur > slow_cur
        bearish_cross = fast_prev >= slow_prev and fast_cur < slow_cur

        snapshot = {
            fast_col: round(fast_cur, 6),
            slow_col: round(slow_cur, 6),
            signal_col: round(signal_ema, 6),
            "close": round(close, 6),
        }

        if bullish_cross:
            above_trend = signal_ema > 0 and close > signal_ema
            if above_trend:
                return SignalResult(
                    signal_value=7,
                    confidence=0.85,
                    indicator_snapshot=snapshot,
                    rule_triggered="ema_bullish_cross_above_trend",
                )
            return SignalResult(
                signal_value=3,
                confidence=0.55,
                indicator_snapshot=snapshot,
                rule_triggered="ema_bullish_cross_below_trend",
            )

        if bearish_cross:
            below_trend = signal_ema > 0 and close < signal_ema
            if below_trend:
                return SignalResult(
                    signal_value=-7,
                    confidence=0.85,
                    indicator_snapshot=snapshot,
                    rule_triggered="ema_bearish_cross_below_trend",
                )
            return SignalResult(
                signal_value=-3,
                confidence=0.55,
                indicator_snapshot=snapshot,
                rule_triggered="ema_bearish_cross_above_trend",
            )

        return SignalResult(
            signal_value=0,
            confidence=0.0,
            indicator_snapshot=snapshot,
            rule_triggered="no_crossover",
        )

    def _warmup_bars(self) -> int:
        return self.params["signal_period"] + 10
