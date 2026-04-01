import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies import DBSession, PaginationParams, require_scope
from app.models.api_key import ApiKey
from app.schemas.common import PaginatedResponse
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate
from app.services import subscription_service

router = APIRouter(prefix="/subscriptions")


@router.get("", response_model=PaginatedResponse[SubscriptionResponse])
async def list_subscriptions(
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
    channel_id: uuid.UUID | None = None,
    strategy_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    pagination: PaginationParams = Depends(),
):
    """List subscriptions with optional filters. Paginated."""
    items, total = await subscription_service.list_subscriptions(
        session,
        channel_id=channel_id,
        strategy_id=strategy_id,
        is_active=is_active,
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


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: SubscriptionCreate,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Create a new subscription linking a channel to a strategy (or all strategies)."""
    return await subscription_service.create_subscription(session, body.model_dump())


@router.get("/{id}", response_model=SubscriptionResponse)
async def get_subscription(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Get a subscription by id."""
    return await subscription_service.get_subscription(session, id)


@router.patch("/{id}", response_model=SubscriptionResponse)
async def update_subscription(
    id: uuid.UUID,
    body: SubscriptionUpdate,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Partially update a subscription."""
    data = body.model_dump(exclude_unset=True)
    return await subscription_service.update_subscription(session, id, data)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Delete a subscription."""
    await subscription_service.delete_subscription(session, id)
