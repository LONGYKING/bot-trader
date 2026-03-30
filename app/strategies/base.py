from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SignalResult:
    signal_value: int  # -7, -3, 0, 3, 7
    confidence: float  # 0.0–1.0
    indicator_snapshot: dict = field(default_factory=dict)
    rule_triggered: str = ""


class BaseStrategy(ABC):
    name: str = ""
    description: str = ""

    def __init__(self, params: dict) -> None:
        self.params = self.validate_params(params)

    @abstractmethod
    def validate_params(self, raw: dict) -> dict: ...

    @abstractmethod
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame: ...

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> SignalResult: ...

    def generate_signal_series(self, df: pd.DataFrame) -> pd.Series:
        enriched = self.compute_indicators(df)
        signals = pd.Series(0, index=df.index, dtype=int)
        warmup = self._warmup_bars()
        for i in range(warmup, len(df)):
            result = self.generate_signal(enriched.iloc[: i + 1])
            signals.iloc[i] = result.signal_value
        return signals

    def _warmup_bars(self) -> int:
        return 50
