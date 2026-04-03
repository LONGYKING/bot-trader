import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.strategy import Strategy
from app.repositories.outcome import OutcomeRepository
from app.repositories.signal import SignalRepository
from app.repositories.strategy import StrategyRepository
from app.strategies.registry import StrategyRegistry


async def create_strategy(
    session: AsyncSession,
    data: dict[str, Any],
    tenant_id: uuid.UUID | None = None,
) -> Strategy:
    strategy_class = data.get("strategy_class", "")
    params = data.get("params", {})

    try:
        StrategyRegistry.instantiate(strategy_class, params)
    except (ValueError, Exception) as exc:
        raise ValidationError(str(exc)) from exc

    repo = StrategyRepository(session, tenant_id)
    name = data.get("name", "")
    existing = await repo.get_by_name(name)
    if existing is not None:
        raise ConflictError(f"Strategy with name '{name}' already exists")

    return await repo.create(data)


async def get_strategy(
    session: AsyncSession,
    id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> Strategy:
    repo = StrategyRepository(session, tenant_id)
    strategy = await repo.get_by_id(id)
    if strategy is None:
        raise NotFoundError("Strategy", str(id))
    return strategy


async def list_strategies(
    session: AsyncSession,
    tenant_id: uuid.UUID | None = None,
    asset: str | None = None,
    timeframe: str | None = None,
    is_active: bool | None = None,
    strategy_class: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Strategy], int]:
    repo = StrategyRepository(session, tenant_id)

    filters: dict[str, Any] = {}
    if asset is not None:
        filters["asset"] = asset
    if timeframe is not None:
        filters["timeframe"] = timeframe
    if is_active is not None:
        filters["is_active"] = is_active
    if strategy_class is not None:
        filters["strategy_class"] = strategy_class

    items = await repo.list(skip=offset, limit=limit, **filters)
    total = await repo.count(**filters)
    return items, total


async def update_strategy(
    session: AsyncSession,
    id: uuid.UUID,
    data: dict[str, Any],
    tenant_id: uuid.UUID | None = None,
) -> Strategy:
    repo = StrategyRepository(session, tenant_id)
    strategy = await repo.get_by_id(id)
    if strategy is None:
        raise NotFoundError("Strategy", str(id))

    new_strategy_class = data.get("strategy_class", strategy.strategy_class)
    new_params = data.get("params", strategy.params)

    params_changed = "params" in data and data["params"] != strategy.params
    class_changed = "strategy_class" in data and data["strategy_class"] != strategy.strategy_class

    if params_changed or class_changed:
        try:
            StrategyRegistry.instantiate(new_strategy_class, new_params)
        except (ValueError, Exception) as exc:
            raise ValidationError(str(exc)) from exc

    if "name" in data and data["name"] != strategy.name:
        existing = await repo.get_by_name(data["name"])
        if existing is not None:
            raise ConflictError(f"Strategy with name '{data['name']}' already exists")

    updated = await repo.update(id, data)
    if updated is None:
        raise NotFoundError("Strategy", str(id))

    if params_changed:
        await repo.increment_version(id)
        await session.refresh(updated)

    return updated


async def delete_strategy(
    session: AsyncSession,
    id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> None:
    repo = StrategyRepository(session, tenant_id)
    strategy = await repo.get_by_id(id)
    if strategy is None:
        raise NotFoundError("Strategy", str(id))
    await repo.update(id, {"is_active": False})


async def get_strategy_performance(
    session: AsyncSession,
    id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> dict:
    await get_strategy(session, id, tenant_id=tenant_id)

    signal_repo = SignalRepository(session, tenant_id)
    outcome_repo = OutcomeRepository(session, tenant_id)

    total_signals = await signal_repo.count_filtered(strategy_id=id)
    profitable_signals = await signal_repo.count_filtered(strategy_id=id, is_profitable=True)
    stats = await outcome_repo.get_stats(strategy_id=id)

    from sqlalchemy import func, select

    from app.models.outcome import SignalOutcome
    from app.models.signal import Signal as SignalModel

    by_regime_stmt = (
        select(
            SignalModel.regime,
            func.count(SignalOutcome.id).label("signal_count"),
            func.avg(SignalOutcome.pnl_pct).label("avg_pnl_pct"),
            func.sum(
                func.cast(SignalOutcome.is_profitable, type_=func.count().type)
            ).label("winning"),
        )
        .join(SignalModel, SignalModel.id == SignalOutcome.signal_id)
        .where(SignalModel.strategy_id == id)
        .group_by(SignalModel.regime)
    )
    regime_result = await session.execute(by_regime_stmt)
    by_regime: dict[str, Any] = {}
    for row in regime_result.all():
        regime_key = row.regime or "unknown"
        count = int(row.signal_count or 0)
        winning = int(row.winning or 0)
        by_regime[regime_key] = {
            "count": count,
            "winning": winning,
            "win_rate": (winning / count) if count > 0 else 0.0,
            "avg_pnl_pct": float(row.avg_pnl_pct) if row.avg_pnl_pct is not None else 0.0,
        }

    win_rate = (profitable_signals / total_signals) if total_signals > 0 else 0.0

    return {
        "total_signals": total_signals,
        "profitable_signals": profitable_signals,
        "win_rate": win_rate,
        "avg_pnl_pct": stats.get("avg_pnl_pct", 0.0),
        "by_regime": by_regime,
    }
