import uuid

from fastapi import APIRouter, Depends, status

from app.core.plan_limits import get_effective_limits
from app.dependencies import CurrentTenant, DBSession, PaginationParams
from app.schemas.common import PaginatedResponse
from app.schemas.signal import SignalResponse
from app.schemas.strategy import (
    StrategyCreate,
    StrategyPerformance,
    StrategyResponse,
    StrategyUpdate,
)
from app.services import strategy_service

router = APIRouter(prefix="/strategies")


@router.get("/classes")
async def list_strategy_classes():
    """Return all registered strategy classes with their names and descriptions."""
    import app.strategies  # noqa: F401 — triggers registration side effects
    from app.strategies.registry import StrategyRegistry

    result = []
    for name in StrategyRegistry.list_all():
        cls = StrategyRegistry.get(name)
        description = getattr(cls, "description", None) or (cls.__doc__ or "").strip().split("\n")[0]
        result.append({"name": name, "description": description})
    return result


@router.get("", response_model=PaginatedResponse[StrategyResponse])
async def list_strategies(
    tenant: CurrentTenant,
    session: DBSession,
    asset: str | None = None,
    timeframe: str | None = None,
    is_active: bool | None = None,
    strategy_class: str | None = None,
    pagination: PaginationParams = Depends(),
):
    items, total = await strategy_service.list_strategies(
        session,
        tenant_id=tenant.id,
        asset=asset,
        timeframe=timeframe,
        is_active=is_active,
        strategy_class=strategy_class,
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(items=items, total=total, page=pagination.page,
                             page_size=pagination.page_size, pages=pages)


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: StrategyCreate,
    tenant: CurrentTenant,
    session: DBSession,
):
    limits = await get_effective_limits(session, tenant)
    limits.check_strategy_class(body.strategy_class)
    from app.repositories.strategy import StrategyRepository
    count = await StrategyRepository(session, tenant.id).count()
    limits.check_capacity("strategies", count)
    data = body.model_dump()
    data["tenant_id"] = tenant.id
    return await strategy_service.create_strategy(session, data, tenant_id=tenant.id)


@router.get("/{id}", response_model=StrategyResponse)
async def get_strategy(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    return await strategy_service.get_strategy(session, id, tenant_id=tenant.id)


@router.patch("/{id}", response_model=StrategyResponse)
async def update_strategy(
    id: uuid.UUID,
    body: StrategyUpdate,
    tenant: CurrentTenant,
    session: DBSession,
):
    data = body.model_dump(exclude_unset=True)
    return await strategy_service.update_strategy(session, id, data, tenant_id=tenant.id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    await strategy_service.delete_strategy(session, id, tenant_id=tenant.id)


@router.get("/{id}/signals", response_model=PaginatedResponse[SignalResponse])
async def list_strategy_signals(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
    pagination: PaginationParams = Depends(),
):
    from app.services import signal_service

    await strategy_service.get_strategy(session, id, tenant_id=tenant.id)
    items, total = await signal_service.list_signals(
        session,
        tenant_id=tenant.id,
        filters={"strategy_id": id},
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(items=items, total=total, page=pagination.page,
                             page_size=pagination.page_size, pages=pages)


@router.get("/{id}/performance", response_model=StrategyPerformance)
async def get_strategy_performance(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    perf = await strategy_service.get_strategy_performance(session, id, tenant_id=tenant.id)
    return StrategyPerformance(strategy_id=id, **perf)
