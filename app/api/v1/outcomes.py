import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import CurrentTenant, DBSession, PaginationParams
from app.schemas.common import PaginatedResponse
from app.schemas.outcome import OutcomeResponse, OutcomeStats
from app.services import outcome_service

router = APIRouter(prefix="/outcomes")


@router.get("", response_model=PaginatedResponse[OutcomeResponse])
async def list_outcomes(
    tenant: CurrentTenant,
    session: DBSession,
    is_profitable: bool | None = None,
    asset: str | None = None,
    strategy_id: uuid.UUID | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
    pagination: PaginationParams = Depends(),
):
    filters: dict = {}
    if is_profitable is not None:
        filters["is_profitable"] = is_profitable
    if asset is not None:
        filters["asset"] = asset
    if strategy_id is not None:
        filters["strategy_id"] = strategy_id

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

    items, total = await outcome_service.list_outcomes(
        session,
        tenant_id=tenant.id,
        filters=filters,
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(items=items, total=total, page=pagination.page,
                             page_size=pagination.page_size, pages=pages)


@router.get("/stats", response_model=OutcomeStats)
async def get_outcome_stats(
    tenant: CurrentTenant,
    session: DBSession,
    asset: str | None = None,
    strategy_id: uuid.UUID | None = None,
):
    stats = await outcome_service.get_stats(
        session, tenant_id=tenant.id, asset=asset, strategy_id=strategy_id
    )
    return OutcomeStats(
        total_count=stats.get("total_count", 0),
        winning_count=stats.get("winning_count", 0),
        win_rate=stats.get("win_rate", 0.0),
        avg_pnl_pct=stats.get("avg_pnl_pct", 0.0),
    )


@router.post("/resolve")
async def resolve_outcomes(
    tenant: CurrentTenant,
    session: DBSession,
):
    resolved_count = await outcome_service.resolve_outcomes(session)
    return {"message": f"Resolved {resolved_count} outcome(s).", "resolved": resolved_count}


@router.get("/{signal_id}", response_model=OutcomeResponse)
async def get_outcome(
    signal_id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    return await outcome_service.get_outcome(session, signal_id, tenant_id=tenant.id)
