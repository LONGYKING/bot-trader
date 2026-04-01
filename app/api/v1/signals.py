import uuid
from datetime import datetime
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status

from app.db.redis import get_arq_pool
from app.dependencies import DBSession, PaginationParams, require_scope
from app.models.api_key import ApiKey
from app.schemas.common import PaginatedResponse
from app.schemas.delivery import DeliveryResponse
from app.schemas.outcome import OutcomeResponse
from app.schemas.signal import (
    SignalForceRequest,
    SignalGenerateRequest,
    SignalResponse,
)
from app.services import delivery_service, outcome_service, signal_service

router = APIRouter(prefix="/signals")


@router.get("", response_model=PaginatedResponse[SignalResponse])
async def list_signals(
    session: DBSession,
    _: ApiKey = Depends(require_scope("read:signals")),
    strategy_id: uuid.UUID | None = None,
    asset: str | None = None,
    signal_value: int | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
    is_profitable: bool | None = None,
    pagination: PaginationParams = Depends(),
):
    """List signals with optional filters. Paginated."""
    filters: dict = {}
    if strategy_id is not None:
        filters["strategy_id"] = strategy_id
    if asset is not None:
        filters["asset"] = asset
    if signal_value is not None:
        filters["signal_value"] = signal_value

    parsed_from = datetime.fromisoformat(from_dt) if from_dt is not None else None
    parsed_to = datetime.fromisoformat(to_dt) if to_dt is not None else None
    if parsed_from is not None and parsed_to is not None and parsed_from > parsed_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_dt must be before to_dt",
        )
    if parsed_from is not None:
        filters["from_dt"] = parsed_from
    if parsed_to is not None:
        filters["to_dt"] = parsed_to

    if is_profitable is not None:
        filters["is_profitable"] = is_profitable

    items, total = await signal_service.list_signals(
        session,
        filters=filters,
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


@router.post("/generate")
async def generate_signal(
    body: SignalGenerateRequest,
    session: DBSession,
    redis: Annotated[ArqRedis, Depends(get_arq_pool)],
    _: ApiKey = Depends(require_scope("write:signals")),
):
    """Trigger immediate signal generation for a strategy."""
    signal = await signal_service.generate_signal(session, redis, body.strategy_id)
    if signal is None:
        return {"message": "No signal generated (neutral)", "signal": None}
    return {"message": "Signal generated", "signal": SignalResponse.model_validate(signal)}


@router.post("/force")
async def force_signal(
    body: SignalForceRequest,
    session: DBSession,
    redis: Annotated[ArqRedis, Depends(get_arq_pool)],
    _: ApiKey = Depends(require_scope("admin")),
):
    """Force a signal with a specific value, bypassing strategy computation.

    Useful for testing delivery pipelines and exchange order execution.
    signal_value must be one of: -7, -3, 3, 7.
    """
    signal = await signal_service.force_signal(
        session, redis, body.strategy_id, body.signal_value, body.entry_price
    )
    return {"message": "Signal forced", "signal": SignalResponse.model_validate(signal)}


@router.get("/{id}", response_model=SignalResponse)
async def get_signal(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("read:signals")),
):
    """Get full signal detail by id."""
    return await signal_service.get_signal(session, id)


@router.get("/{id}/deliveries", response_model=list[DeliveryResponse])
async def get_signal_deliveries(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("read:signals")),
):
    """Return all delivery attempts for a signal."""
    # Ensure signal exists first
    await signal_service.get_signal(session, id)
    return await delivery_service.get_deliveries_for_signal(session, id)


@router.get("/{id}/outcome", response_model=OutcomeResponse)
async def get_signal_outcome(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("read:signals")),
):
    """Return the outcome for a specific signal."""
    return await outcome_service.get_outcome(session, id)
