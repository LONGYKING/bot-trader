"""Outcome resolution service.

Responsible for:
- Computing final P&L for expired unresolved signals.
- Persisting SignalOutcome records.
- Marking Signal.is_profitable.
"""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.market_data import fetch_ohlcv
from app.exceptions import NotFoundError
from app.models.outcome import SignalOutcome
from app.repositories.outcome import OutcomeRepository
from app.repositories.signal import SignalRepository

# Default profit cap if not specified on the signal
_DEFAULT_PROFIT_CAP = 0.10


def _compute_pnl(
    direction: str,
    entry_price: float,
    exit_price: float,
    profit_cap_pct: float | None,
) -> float:
    """Compute capped P&L percentage.

    CALL: pnl = (exit - entry) / entry
    PUT:  pnl = (entry - exit) / entry
    """
    if direction == "call":
        pnl = (exit_price - entry_price) / entry_price
    else:
        pnl = (entry_price - exit_price) / entry_price

    cap = float(profit_cap_pct) if profit_cap_pct is not None else _DEFAULT_PROFIT_CAP
    return min(pnl, cap)


async def _fetch_close_at(
    exchange: str,
    asset: str,
    timeframe: str,
    target_time: datetime,
) -> float:
    """Fetch the close price of the candle just at or before *target_time*.

    Uses a 1-bar-wide window starting one candle before the target.
    """
    # Request 2 bars ending around target_time to be safe
    since = target_time - timedelta(hours=1)
    df = await fetch_ohlcv(
        exchange_id=exchange,
        symbol=asset,
        timeframe=timeframe,
        limit=2,
        since=since,
    )
    # Return the close of the last available bar
    return float(df["close"].iloc[-1])


async def resolve_outcomes(session: AsyncSession) -> list[dict]:
    """Compute outcomes for all expired unresolved signals.

    Steps:
        1. Fetch unresolved expired signals (expiry_time < now, is_profitable IS NULL).
        2. Group by (exchange, asset, timeframe) to batch market-data calls.
        3. For each group fetch exit price at expiry via ccxt.
        4. Compute pnl_pct and is_profitable.
        5. Bulk insert SignalOutcome records.
        6. Bulk update Signal.is_profitable.

    Returns list of resolved outcome dicts (for downstream notifications).
    """
    now = datetime.now(UTC)
    signal_repo = SignalRepository(session)
    outcome_repo = OutcomeRepository(session)

    expired_signals = await signal_repo.get_unresolved_expired(now)
    if not expired_signals:
        return []

    # Load strategies to get exchange info: strategy_id -> strategy
    from app.repositories.strategy import StrategyRepository
    strategy_repo = StrategyRepository(session)

    # Batch-load all required strategies in one query
    unique_strategy_ids = list({s.strategy_id for s in expired_signals})
    strategies = await strategy_repo.get_by_ids(unique_strategy_ids)

    # Group signals by (exchange, asset, timeframe, expiry_time) for price fetching
    # We build a lookup of (exchange, asset, timeframe, expiry_time) -> exit_price
    price_cache: dict[tuple, float] = {}

    outcomes_to_insert: list[dict] = []
    resolved_ids: list[uuid.UUID] = []
    profitable_values: dict[uuid.UUID, bool] = {}

    for signal in expired_signals:
        strat = strategies.get(signal.strategy_id)
        if strat is None:
            # Cannot resolve without strategy/exchange info
            continue

        expiry = signal.expiry_time
        if expiry is None:
            continue
        cache_key = (strat.exchange, signal.asset, signal.timeframe, expiry)

        if cache_key not in price_cache:
            try:
                exit_price = await _fetch_close_at(
                    exchange=strat.exchange,
                    asset=signal.asset,
                    timeframe=signal.timeframe,
                    target_time=expiry,
                )
                price_cache[cache_key] = exit_price
            except Exception:  # noqa: BLE001
                # Skip this signal if market data unavailable
                continue

        exit_price = price_cache[cache_key]
        entry_price = float(signal.entry_price) if signal.entry_price is not None else 0.0

        if entry_price == 0.0:
            continue

        direction = signal.direction or ("call" if (signal.signal_value or 0) > 0 else "put")
        pnl_pct = _compute_pnl(direction, entry_price, exit_price, signal.profit_cap_pct)
        is_profitable = pnl_pct > 0.0

        computed_at = now
        outcomes_to_insert.append(
            {
                "signal_id": signal.id,
                "exit_price": exit_price,
                "exit_time": expiry,
                "pnl_pct": pnl_pct,
                "is_profitable": is_profitable,
                "regime_at_exit": None,
                "computed_at": computed_at,
            }
        )
        resolved_ids.append(signal.id)
        profitable_values[signal.id] = is_profitable

    if not outcomes_to_insert:
        return []

    await outcome_repo.bulk_insert(outcomes_to_insert)
    await signal_repo.bulk_mark_profitable(resolved_ids, profitable_values)

    # Build rich outcome dicts for downstream notification delivery
    signal_map = {s.id: s for s in expired_signals}
    resolved_outcomes: list[dict] = []
    for o in outcomes_to_insert:
        sig = signal_map.get(o["signal_id"])
        if sig is None:
            continue
        resolved_outcomes.append({
            "signal_id": str(o["signal_id"]),
            "asset": sig.asset,
            "direction": sig.direction or ("call" if (sig.signal_value or 0) > 0 else "put"),
            "tenor_days": sig.tenor_days,
            "entry_price": float(sig.entry_price) if sig.entry_price is not None else None,
            "exit_price": float(o["exit_price"]),
            "pnl_pct": round(float(o["pnl_pct"]) * 100, 2),
            "is_profitable": o["is_profitable"],
            "entry_time": sig.entry_time.isoformat() if sig.entry_time else None,
            "exit_time": o["exit_time"].isoformat() if o["exit_time"] else None,
        })

    return resolved_outcomes


async def get_outcome(
    session: AsyncSession,
    signal_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> SignalOutcome:
    """Return the outcome for a signal. Raises NotFoundError if not found."""
    repo = OutcomeRepository(session, tenant_id)
    outcome = await repo.get_by_signal(signal_id)
    if outcome is None:
        raise NotFoundError("SignalOutcome", str(signal_id))
    return outcome


async def list_outcomes(
    session: AsyncSession,
    filters: dict,
    limit: int = 50,
    offset: int = 0,
    tenant_id: uuid.UUID | None = None,
) -> tuple[list[SignalOutcome], int]:
    """Return (items, total_count) with optional filters."""
    repo = OutcomeRepository(session, tenant_id)
    items = await repo.list_filtered(
        is_profitable=filters.get("is_profitable"),
        asset=filters.get("asset"),
        strategy_id=filters.get("strategy_id"),
        from_dt=filters.get("from_dt"),
        to_dt=filters.get("to_dt"),
        limit=limit,
        offset=offset,
    )
    stats = await repo.get_stats(
        asset=filters.get("asset"),
        strategy_id=filters.get("strategy_id"),
    )
    if filters.get("is_profitable") is not None or filters.get("from_dt") is not None or filters.get("to_dt") is not None:
        all_items = await repo.list_filtered(
            is_profitable=filters.get("is_profitable"),
            asset=filters.get("asset"),
            strategy_id=filters.get("strategy_id"),
            from_dt=filters.get("from_dt"),
            to_dt=filters.get("to_dt"),
            limit=100_000,
            offset=0,
        )
        total = len(all_items)
    else:
        total = stats.get("total_count", len(items))

    return items, total


async def get_stats(
    session: AsyncSession,
    asset: str | None = None,
    strategy_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> dict:
    """Return aggregated outcome stats: win_rate, avg_pnl_pct, total_count, winning_count."""
    repo = OutcomeRepository(session, tenant_id)
    return await repo.get_stats(asset=asset, strategy_id=strategy_id)
