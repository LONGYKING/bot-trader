import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import PaginationParams, require_scope
from app.models.api_key import ApiKey
from app.schemas.common import PaginatedResponse
from app.schemas.signal import SignalResponse
from app.schemas.strategy import StrategyCreate, StrategyPerformance, StrategyResponse, StrategyUpdate
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
    asset: str | None = None,
    timeframe: str | None = None,
    is_active: bool | None = None,
    strategy_class: str | None = None,
    pagination: PaginationParams = Depends(),
    session: Annotated[AsyncSession, Depends(get_db)] = None,
    _: ApiKey = Depends(require_scope("read:strategies")),
):
    """List strategies with optional filters. Paginated."""
    items, total = await strategy_service.list_strategies(
        session,
        asset=asset,
        timeframe=timeframe,
        is_active=is_active,
        strategy_class=strategy_class,
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
    )


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: StrategyCreate,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
    _: ApiKey = Depends(require_scope("write:strategies")),
):
    """Create a new strategy."""
    return await strategy_service.create_strategy(session, body.model_dump())


@router.get("/{id}", response_model=StrategyResponse)
async def get_strategy(
    id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
    _: ApiKey = Depends(require_scope("read:strategies")),
):
    """Get a strategy by id."""
    return await strategy_service.get_strategy(session, id)


@router.patch("/{id}", response_model=StrategyResponse)
async def update_strategy(
    id: uuid.UUID,
    body: StrategyUpdate,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
    _: ApiKey = Depends(require_scope("write:strategies")),
):
    """Partially update a strategy."""
    data = body.model_dump(exclude_unset=True)
    return await strategy_service.update_strategy(session, id, data)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
    _: ApiKey = Depends(require_scope("write:strategies")),
):
    """Soft-delete a strategy (sets is_active=False)."""
    await strategy_service.delete_strategy(session, id)


@router.get("/{id}/signals", response_model=PaginatedResponse[SignalResponse])
async def list_strategy_signals(
    id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    session: Annotated[AsyncSession, Depends(get_db)] = None,
    _: ApiKey = Depends(require_scope("read:strategies")),
):
    """List all signals for a specific strategy. Paginated."""
    from app.services import signal_service

    # Ensure strategy exists first
    await strategy_service.get_strategy(session, id)

    items, total = await signal_service.list_signals(
        session,
        filters={"strategy_id": id},
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
    )


@router.get("/{id}/performance", response_model=StrategyPerformance)
async def get_strategy_performance(
    id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
    _: ApiKey = Depends(require_scope("read:strategies")),
):
    """Return performance summary for a strategy."""
    perf = await strategy_service.get_strategy_performance(session, id)
    return StrategyPerformance(strategy_id=id, **perf)
