"""
Unit tests for StrategyRegistry.

Verifies that all 6 built-in strategies are registered and that the registry
API works correctly (get, list_all, instantiate, error cases).
"""
from __future__ import annotations

import pytest

# Importing the strategies package triggers all @StrategyRegistry.register decorators
import app.strategies  # noqa: F401

from app.strategies.registry import StrategyRegistry
from app.strategies.macd_rsi import MacdRsiStrategy
from app.strategies.bollinger_breakout import BollingerBreakoutStrategy
from app.strategies.rsi_divergence import RsiDivergenceStrategy
from app.strategies.ema_crossover import EmaCrossoverStrategy
from app.strategies.adx_trend import AdxTrendStrategy
from app.strategies.vwap_reversion import VwapReversionStrategy


EXPECTED_STRATEGIES = {
    "macd_rsi",
    "bollinger_breakout",
    "rsi_divergence",
    "ema_crossover",
    "adx_trend",
    "vwap_reversion",
}


class TestStrategyRegistryRegistration:
    def test_all_six_strategies_registered(self):
        registered = set(StrategyRegistry.list_all())
        assert EXPECTED_STRATEGIES.issubset(registered), (
            f"Missing strategies: {EXPECTED_STRATEGIES - registered}"
        )

    def test_list_all_returns_sorted(self):
        names = StrategyRegistry.list_all()
        assert names == sorted(names)

    def test_get_macd_rsi_returns_correct_class(self):
        cls = StrategyRegistry.get("macd_rsi")
        assert cls is MacdRsiStrategy

    def test_get_bollinger_breakout(self):
        cls = StrategyRegistry.get("bollinger_breakout")
        assert cls is BollingerBreakoutStrategy

    def test_get_rsi_divergence(self):
        cls = StrategyRegistry.get("rsi_divergence")
        assert cls is RsiDivergenceStrategy

    def test_get_ema_crossover(self):
        cls = StrategyRegistry.get("ema_crossover")
        assert cls is EmaCrossoverStrategy

    def test_get_adx_trend(self):
        cls = StrategyRegistry.get("adx_trend")
        assert cls is AdxTrendStrategy

    def test_get_vwap_reversion(self):
        cls = StrategyRegistry.get("vwap_reversion")
        assert cls is VwapReversionStrategy


class TestStrategyRegistryGet:
    def test_invalid_name_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            StrategyRegistry.get("nonexistent_strategy_xyz")

    def test_error_message_lists_available(self):
        with pytest.raises(ValueError, match="macd_rsi"):
            StrategyRegistry.get("nonexistent_strategy_xyz")


class TestStrategyRegistryInstantiate:
    def test_instantiate_macd_rsi_with_empty_params(self):
        instance = StrategyRegistry.instantiate("macd_rsi", {})
        assert isinstance(instance, MacdRsiStrategy)

    def test_instantiate_bollinger_breakout_with_empty_params(self):
        instance = StrategyRegistry.instantiate("bollinger_breakout", {})
        assert isinstance(instance, BollingerBreakoutStrategy)

    def test_instantiate_rsi_divergence_with_empty_params(self):
        instance = StrategyRegistry.instantiate("rsi_divergence", {})
        assert isinstance(instance, RsiDivergenceStrategy)

    def test_instantiate_ema_crossover_with_empty_params(self):
        instance = StrategyRegistry.instantiate("ema_crossover", {})
        assert isinstance(instance, EmaCrossoverStrategy)

    def test_instantiate_adx_trend_with_empty_params(self):
        instance = StrategyRegistry.instantiate("adx_trend", {})
        assert isinstance(instance, AdxTrendStrategy)

    def test_instantiate_vwap_reversion_with_empty_params(self):
        instance = StrategyRegistry.instantiate("vwap_reversion", {})
        assert isinstance(instance, VwapReversionStrategy)

    def test_instantiate_with_valid_param_override(self):
        instance = StrategyRegistry.instantiate("macd_rsi", {"rsi_period": 21})
        assert instance.params["rsi_period"] == 21

    def test_instantiate_invalid_name_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            StrategyRegistry.instantiate("ghost_strategy", {})
