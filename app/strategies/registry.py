from __future__ import annotations

from app.strategies.base import BaseStrategy


class StrategyRegistry:
    _registry: dict[str, type[BaseStrategy]] = {}

    @classmethod
    def register(cls, strategy_cls: type[BaseStrategy]) -> type[BaseStrategy]:
        """
        Class decorator that registers a strategy by its ``name`` attribute.

        Usage::

            @StrategyRegistry.register
            class MyStrategy(BaseStrategy):
                name = "my_strategy"
                ...
        """
        key = strategy_cls.name
        if not key:
            raise ValueError(
                f"Strategy class {strategy_cls.__name__} must define a non-empty `name` attribute."
            )
        if key in cls._registry:
            raise ValueError(
                f"A strategy with name '{key}' is already registered "
                f"({cls._registry[key].__name__}). Use a unique name."
            )
        cls._registry[key] = strategy_cls
        return strategy_cls

    @classmethod
    def get(cls, name: str) -> type[BaseStrategy]:
        """Return the strategy class registered under *name*."""
        if name not in cls._registry:
            raise ValueError(
                f"Unknown strategy '{name}'. "
                f"Available strategies: {list(cls._registry.keys())}"
            )
        return cls._registry[name]

    @classmethod
    def list_all(cls) -> list[str]:
        """Return a sorted list of all registered strategy names."""
        return sorted(cls._registry.keys())

    @classmethod
    def instantiate(cls, name: str, params: dict) -> BaseStrategy:
        """
        Instantiate a registered strategy with the given *params* dict.

        Parameters
        ----------
        name:
            Registered strategy name (e.g. ``"macd_rsi"``).
        params:
            Parameter overrides.  Missing keys fall back to strategy defaults.
        """
        strategy_cls = cls.get(name)
        return strategy_cls(params)
