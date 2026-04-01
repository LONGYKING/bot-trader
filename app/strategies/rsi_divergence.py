"""
RSI Divergence strategy.

Signal rules
------------
Bullish divergence: price makes a lower low but RSI makes a higher low
  → +7 if RSI < rsi_low (confirmed oversold divergence)
  → +3 if mild bullish divergence (RSI not deep enough but pattern holds)

Bearish divergence: price makes a higher high but RSI makes a lower high
  → -7 if RSI > rsi_high (confirmed overbought divergence)
  → -3 if mild bearish divergence
"""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field

from app.core.indicators import add_rsi
from app.strategies.base import BaseStrategy, SignalResult
from app.strategies.registry import StrategyRegistry

# ---------------------------------------------------------------------------
# Parameter model
# ---------------------------------------------------------------------------

class RsiDivergenceParams(BaseModel):
    rsi_period: int = Field(default=14, ge=2, le=100, description="RSI look-back period")
    lookback: int = Field(
        default=10,
        ge=3,
        le=50,
        description="Number of bars to scan for divergence pivot points",
    )
    rsi_low: float = Field(
        default=40.0,
        ge=10.0,
        le=50.0,
        description="RSI threshold below which a bullish divergence is 'confirmed'",
    )
    rsi_high: float = Field(
        default=60.0,
        ge=50.0,
        le=90.0,
        description="RSI threshold above which a bearish divergence is 'confirmed'",
    )

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

@StrategyRegistry.register
class RsiDivergenceStrategy(BaseStrategy):
    name = "rsi_divergence"
    description = (
        "Detects price/RSI divergences and generates reversal signals. "
        "Strong signals (+7/-7) are issued when RSI is in extreme territory; "
        "mild divergences produce weak signals (+3/-3)."
    )

    def validate_params(self, raw: dict) -> dict:
        return RsiDivergenceParams(**raw).model_dump()

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        return add_rsi(df, period=self.params["rsi_period"])

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        p = self.params
        warmup = self._warmup_bars()
        if len(df) < warmup:
            return SignalResult(signal_value=0, confidence=0.0, rule_triggered="warmup")

        lookback = p["lookback"]
        # Work with the last (lookback + 1) bars so we have a reference window
        window = df.iloc[-(lookback + 1):]

        prices = window["close"].values
        rsi_vals = window["rsi"].values

        # Current (last) bar
        cur_price = float(prices[-1])
        cur_rsi = float(rsi_vals[-1])

        # Reference window: all bars except the last
        ref_prices = prices[:-1]
        ref_rsi = rsi_vals[:-1]

        snapshot = {
            "close": round(cur_price, 6),
            "rsi": round(cur_rsi, 2),
            "lookback": lookback,
        }

        # --- Bullish divergence check ---
        # Price makes a lower low compared to the minimum of the reference window
        # but RSI is higher than the RSI at that price minimum
        ref_price_min_idx = int(ref_prices.argmin())
        ref_price_min = float(ref_prices[ref_price_min_idx])
        ref_rsi_at_min = float(ref_rsi[ref_price_min_idx])

        bullish_divergence = cur_price < ref_price_min and cur_rsi > ref_rsi_at_min

        if bullish_divergence:
            if cur_rsi < p["rsi_low"]:
                return SignalResult(
                    signal_value=7,
                    confidence=min(0.9, (p["rsi_low"] - cur_rsi) / p["rsi_low"] + 0.5),
                    indicator_snapshot=snapshot,
                    rule_triggered="bullish_divergence_confirmed_oversold",
                )
            return SignalResult(
                signal_value=3,
                confidence=0.5,
                indicator_snapshot=snapshot,
                rule_triggered="bullish_divergence_mild",
            )

        # --- Bearish divergence check ---
        ref_price_max_idx = int(ref_prices.argmax())
        ref_price_max = float(ref_prices[ref_price_max_idx])
        ref_rsi_at_max = float(ref_rsi[ref_price_max_idx])

        bearish_divergence = cur_price > ref_price_max and cur_rsi < ref_rsi_at_max

        if bearish_divergence:
            if cur_rsi > p["rsi_high"]:
                return SignalResult(
                    signal_value=-7,
                    confidence=min(0.9, (cur_rsi - p["rsi_high"]) / (100 - p["rsi_high"]) + 0.5),
                    indicator_snapshot=snapshot,
                    rule_triggered="bearish_divergence_confirmed_overbought",
                )
            return SignalResult(
                signal_value=-3,
                confidence=0.5,
                indicator_snapshot=snapshot,
                rule_triggered="bearish_divergence_mild",
            )

        return SignalResult(
            signal_value=0,
            confidence=0.0,
            indicator_snapshot=snapshot,
            rule_triggered="no_divergence",
        )

    def _warmup_bars(self) -> int:
        p = self.params
        return p["rsi_period"] + p["lookback"] + 10
