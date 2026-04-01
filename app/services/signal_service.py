import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.market_data import fetch_ohlcv
from app.core.regime_detector import classify_regime
from app.exceptions import NotFoundError
from app.models.signal import Signal
from app.repositories.signal import SignalRepository
from app.repositories.strategy import StrategyRepository
from app.services import delivery_service
from app.strategies.registry import StrategyRegistry
from app.types.signal import VALID_SIGNAL_VALUES
from app.types.strategy import StrategyRiskConfig

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_direction_and_tenor(
    trade_type: str, signal_value: int
) -> tuple[str, int | None, datetime | None]:
    """Return ``(direction, tenor_days, expiry_time)`` for a given trade type and value."""
    now = datetime.now(UTC)
    if trade_type == "options":
        tenor_days = 7 if abs(signal_value) == 7 else 3  # noqa: PLR2004
        return (
            "call" if signal_value > 0 else "put",
            tenor_days,
            now + timedelta(days=tenor_days),
        )
    # spot / futures
    return "long" if signal_value > 0 else "short", None, None


def _build_signal_dict(
    *,
    strategy_id: uuid.UUID,
    asset: str,
    timeframe: str,
    signal_value: int,
    trade_type: str,
    confidence: float | None,
    regime: str,
    entry_price: float | None,
    indicator_snapshot: dict,
    rule_triggered: str,
) -> dict:
    """Build the data dict passed to :meth:`~app.repositories.signal.SignalRepository.create`.

    Centralises field construction so both ``generate_signal`` and
    ``force_signal`` stay in sync without duplicating logic.
    """
    now = datetime.now(UTC)
    direction, tenor_days, expiry_time = _resolve_direction_and_tenor(trade_type, signal_value)
    return {
        "strategy_id": strategy_id,
        "asset": asset,
        "timeframe": timeframe,
        "signal_value": signal_value,
        "trade_type": trade_type,
        "direction": direction,
        "tenor_days": tenor_days,
        "confidence": confidence,
        "regime": regime,
        "entry_price": entry_price,
        "entry_time": now,
        "expiry_time": expiry_time,
        "indicator_snapshot": indicator_snapshot,
        "rule_triggered": rule_triggered,
        "created_at": now,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_signal(
    session: AsyncSession,
    arq_pool: object,
    strategy_id: uuid.UUID,
) -> Signal | None:
    """Full signal generation pipeline.

    Steps:
        1. Load strategy from DB.
        2. Fetch OHLCV via :func:`~app.core.market_data.fetch_ohlcv`.
        3. Instantiate strategy class and run ``compute_indicators`` + ``generate_signal``.
        4. Apply strategy ``risk_config`` gates (confidence, daily cap, cooldown).
        5. Classify regime.
        6. If ``signal_value != 0``: persist ``Signal`` and enqueue delivery job.

    Returns:
        The persisted :class:`~app.models.signal.Signal`, or ``None`` if the
        strategy returned ``signal_value == 0`` or a risk gate vetoed it.
    """
    strategy_repo = StrategyRepository(session)
    strategy = await strategy_repo.get_by_id(strategy_id)
    if strategy is None:
        raise NotFoundError("Strategy", str(strategy_id))

    df = await fetch_ohlcv(
        exchange_id=strategy.exchange,
        symbol=strategy.asset,
        timeframe=strategy.timeframe,
        limit=500,
    )

    instance = StrategyRegistry.instantiate(strategy.strategy_class, strategy.params)
    enriched_df = instance.compute_indicators(df)
    signal_result = instance.generate_signal(enriched_df)

    # --- Strategy risk_config gates ---
    risk = StrategyRiskConfig.model_validate(getattr(strategy, "risk_config", None) or {})

    if risk.min_confidence_threshold is not None:
        if (signal_result.confidence or 0) < risk.min_confidence_threshold:
            return None

    if risk.max_daily_signals is not None and arq_pool is not None:
        daily_key = f"signal:daily_count:{strategy_id}:{datetime.now(UTC).date().isoformat()}"
        pipe = arq_pool.pipeline()  # type: ignore[attr-defined]
        pipe.incr(daily_key)
        pipe.expire(daily_key, 86400)
        results = await pipe.execute()
        if results[0] > risk.max_daily_signals:
            return None

    if risk.cooldown_minutes is not None and arq_pool is not None:
        cooldown_key = f"signal:cooldown:{strategy_id}"
        if await arq_pool.exists(cooldown_key):  # type: ignore[attr-defined]
            return None
        await arq_pool.set(cooldown_key, "1", ex=int(risk.cooldown_minutes * 60))  # type: ignore[attr-defined]

    # Neutral — optionally notify subscribers
    if signal_result.signal_value == 0:
        if get_settings().send_neutral_signals:
            regime = classify_regime(enriched_df)
            await arq_pool.enqueue_job(  # type: ignore[attr-defined]
                "notify_neutral",
                strategy_id=str(strategy_id),
                asset=strategy.asset,
                timeframe=strategy.timeframe,
                current_price=float(df["close"].iloc[-1]),
                regime=regime,
                indicator_snapshot=signal_result.indicator_snapshot,
            )
        return None

    regime = classify_regime(enriched_df)
    trade_type = getattr(strategy, "trade_type", "options") or "options"
    entry_price = float(df["close"].iloc[-1])

    signal_repo = SignalRepository(session)
    signal = await signal_repo.create(
        _build_signal_dict(
            strategy_id=strategy_id,
            asset=strategy.asset,
            timeframe=strategy.timeframe,
            signal_value=signal_result.signal_value,
            trade_type=trade_type,
            confidence=signal_result.confidence,
            regime=regime,
            entry_price=entry_price,
            indicator_snapshot=signal_result.indicator_snapshot or {},
            rule_triggered=signal_result.rule_triggered,
        )
    )

    await delivery_service.fan_out_signal(session, signal.id)
    await arq_pool.enqueue_job("deliver_signal", signal_id=str(signal.id))  # type: ignore[attr-defined]
    return signal


async def force_signal(
    session: AsyncSession,
    arq_pool: object,
    strategy_id: uuid.UUID,
    signal_value: int = 7,
    entry_price: float | None = None,
) -> Signal:
    """Create and deliver a signal with an arbitrary ``signal_value``.

    Bypasses strategy computation and market data fetching entirely — useful
    for testing the full delivery pipeline (including exchange order execution)
    on demand.

    Args:
        signal_value: Must be one of ``-7``, ``-3``, ``3``, or ``7``.
        entry_price:  Optional override; leave ``None`` to record without a price.
    """
    if signal_value not in VALID_SIGNAL_VALUES:
        raise ValueError(
            f"signal_value must be one of {sorted(VALID_SIGNAL_VALUES)}. Got {signal_value}"
        )

    strategy_repo = StrategyRepository(session)
    strategy = await strategy_repo.get_by_id(strategy_id)
    if strategy is None:
        raise NotFoundError("Strategy", str(strategy_id))

    trade_type = getattr(strategy, "trade_type", "options") or "options"

    signal_repo = SignalRepository(session)
    signal = await signal_repo.create(
        _build_signal_dict(
            strategy_id=strategy_id,
            asset=strategy.asset,
            timeframe=strategy.timeframe,
            signal_value=signal_value,
            trade_type=trade_type,
            confidence=1.0,
            regime="forced",
            entry_price=entry_price,
            indicator_snapshot={"forced": True},
            rule_triggered="manual_force",
        )
    )

    await delivery_service.fan_out_signal(session, signal.id)
    await arq_pool.enqueue_job("deliver_signal", signal_id=str(signal.id))  # type: ignore[attr-defined]
    return signal


async def list_signals(
    session: AsyncSession,
    filters: dict,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Signal], int]:
    """Return ``(items, total_count)`` with optional filters.

    Supported filter keys: ``strategy_id``, ``asset``, ``signal_value``,
    ``from_dt``, ``to_dt``, ``is_profitable``.
    """
    repo = SignalRepository(session)
    items = await repo.list_filtered(
        strategy_id=filters.get("strategy_id"),
        asset=filters.get("asset"),
        signal_value=filters.get("signal_value"),
        from_dt=filters.get("from_dt"),
        to_dt=filters.get("to_dt"),
        is_profitable=filters.get("is_profitable"),
        limit=limit,
        offset=offset,
    )
    total = await repo.count_filtered(
        strategy_id=filters.get("strategy_id"),
        asset=filters.get("asset"),
        signal_value=filters.get("signal_value"),
        from_dt=filters.get("from_dt"),
        to_dt=filters.get("to_dt"),
        is_profitable=filters.get("is_profitable"),
    )
    return items, total


async def get_signal(session: AsyncSession, id: uuid.UUID) -> Signal:
    """Return signal by id.  Raises :exc:`~app.exceptions.NotFoundError` if missing."""
    repo = SignalRepository(session)
    signal = await repo.get_by_id(id)
    if signal is None:
        raise NotFoundError("Signal", str(id))
    return signal
