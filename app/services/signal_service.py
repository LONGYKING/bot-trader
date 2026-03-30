import uuid
from datetime import datetime, timedelta, timezone

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


def _compute_expiry(signal_value: int, entry_time: datetime) -> datetime:
    """Compute expiry_time from signal value: 7 days for ±7, 3 days for ±3."""
    tenor_days = 7 if abs(signal_value) == 7 else 3
    return entry_time + timedelta(days=tenor_days)


async def generate_signal(
    session: AsyncSession,
    arq_pool: object,
    strategy_id: uuid.UUID,
) -> Signal | None:
    """Full signal generation pipeline.

    Steps:
        1. Load strategy from DB.
        2. Fetch OHLCV via market_data.fetch_ohlcv.
        3. Instantiate strategy class and compute_indicators + generate_signal.
        4. Classify regime.
        5. If signal_value != 0: persist Signal and enqueue delivery job.
        6. Return Signal or None if neutral.

    Returns:
        The persisted Signal, or None if the strategy returned signal_value == 0.
    """
    strategy_repo = StrategyRepository(session)
    strategy = await strategy_repo.get_by_id(strategy_id)
    if strategy is None:
        raise NotFoundError("Strategy", str(strategy_id))

    # 1. Fetch market data
    df = await fetch_ohlcv(
        exchange_id=strategy.exchange,
        symbol=strategy.asset,
        timeframe=strategy.timeframe,
        limit=500,
    )

    # 2. Instantiate strategy and compute signal
    instance = StrategyRegistry.instantiate(strategy.strategy_class, strategy.params)
    enriched_df = instance.compute_indicators(df)
    signal_result = instance.generate_signal(enriched_df)

    # Neutral — optionally notify subscribers so they feel something is happening
    if signal_result.signal_value == 0:
        if get_settings().send_neutral_signals:
            regime = classify_regime(enriched_df)
            await arq_pool.enqueue_job(
                "notify_neutral",
                strategy_id=str(strategy_id),
                asset=strategy.asset,
                timeframe=strategy.timeframe,
                current_price=float(df["close"].iloc[-1]),
                regime=regime,
                indicator_snapshot=signal_result.indicator_snapshot,
            )
        return None

    # 3. Classify regime on enriched data
    regime = classify_regime(enriched_df)

    # 4. Determine entry price, direction, and expiry based on trade_type
    now = datetime.now(timezone.utc)
    entry_price = float(df["close"].iloc[-1])
    trade_type = getattr(strategy, "trade_type", "options") or "options"

    if trade_type == "options":
        tenor_days = 7 if abs(signal_result.signal_value) == 7 else 3
        expiry_time = now + timedelta(days=tenor_days)
        direction = "call" if signal_result.signal_value > 0 else "put"
    else:
        # spot / futures — no fixed tenor or expiry
        tenor_days = None
        expiry_time = None
        direction = "long" if signal_result.signal_value > 0 else "short"

    signal_repo = SignalRepository(session)
    signal = await signal_repo.create(
        {
            "strategy_id": strategy_id,
            "asset": strategy.asset,
            "timeframe": strategy.timeframe,
            "signal_value": signal_result.signal_value,
            "trade_type": trade_type,
            "direction": direction,
            "tenor_days": tenor_days,
            "confidence": signal_result.confidence,
            "regime": regime,
            "entry_price": entry_price,
            "entry_time": now,
            "expiry_time": expiry_time,
            "indicator_snapshot": signal_result.indicator_snapshot,
            "rule_triggered": signal_result.rule_triggered,
            "created_at": now,
        }
    )

    # 5. Create delivery records for all matching subscriptions
    await delivery_service.fan_out_signal(session, signal.id)

    # 6. Enqueue the delivery worker to process those records
    await arq_pool.enqueue_job("deliver_signal", signal_id=str(signal.id))

    return signal


async def force_signal(
    session: AsyncSession,
    arq_pool: object,
    strategy_id: uuid.UUID,
    signal_value: int = 7,
    entry_price: float | None = None,
) -> Signal:
    """Create and deliver a signal with an arbitrary signal_value.

    Bypasses strategy computation and market data fetching entirely — useful
    for testing the full delivery pipeline (including exchange order execution)
    on demand. Pass entry_price explicitly or leave None.
    """
    if signal_value not in (-7, -3, 3, 7):
        raise ValueError(f"signal_value must be one of -7, -3, 3, 7. Got {signal_value}")

    strategy_repo = StrategyRepository(session)
    strategy = await strategy_repo.get_by_id(strategy_id)
    if strategy is None:
        raise NotFoundError("Strategy", str(strategy_id))

    now = datetime.now(timezone.utc)

    trade_type = getattr(strategy, "trade_type", "options") or "options"

    if trade_type == "options":
        tenor_days = 7 if abs(signal_value) == 7 else 3
        expiry_time = now + timedelta(days=tenor_days)
        direction = "call" if signal_value > 0 else "put"
    else:
        tenor_days = None
        expiry_time = None
        direction = "long" if signal_value > 0 else "short"

    signal_repo = SignalRepository(session)
    signal = await signal_repo.create(
        {
            "strategy_id": strategy_id,
            "asset": strategy.asset,
            "timeframe": strategy.timeframe,
            "signal_value": signal_value,
            "trade_type": trade_type,
            "direction": direction,
            "tenor_days": tenor_days,
            "confidence": 1.0,
            "regime": "forced",
            "entry_price": entry_price,
            "entry_time": now,
            "expiry_time": expiry_time,
            "indicator_snapshot": {"forced": True},
            "rule_triggered": "manual_force",
            "created_at": now,
        }
    )

    # Create delivery records then dispatch the worker
    await delivery_service.fan_out_signal(session, signal.id)
    await arq_pool.enqueue_job("deliver_signal", signal_id=str(signal.id))
    return signal


async def list_signals(
    session: AsyncSession,
    filters: dict,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Signal], int]:
    """Return (items, total_count) with optional filters.

    Supported filter keys: strategy_id, asset, signal_value, from_dt, to_dt,
    is_profitable.
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
    """Return signal by id. Raises NotFoundError if not found."""
    repo = SignalRepository(session)
    signal = await repo.get_by_id(id)
    if signal is None:
        raise NotFoundError("Signal", str(id))
    return signal
