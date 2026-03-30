import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.subscription import Subscription
from app.repositories.channel import ChannelRepository
from app.repositories.strategy import StrategyRepository
from app.repositories.subscription import SubscriptionRepository


async def create_subscription(
    session: AsyncSession,
    data: dict[str, Any],
) -> Subscription:
    """Create a subscription. Validates that referenced channel and strategy exist."""
    channel_id = data.get("channel_id")
    strategy_id = data.get("strategy_id")

    channel_repo = ChannelRepository(session)
    channel = await channel_repo.get_by_id(channel_id)
    if channel is None:
        raise NotFoundError("Channel", str(channel_id))

    if strategy_id is not None:
        strategy_repo = StrategyRepository(session)
        strategy = await strategy_repo.get_by_id(strategy_id)
        if strategy is None:
            raise NotFoundError("Strategy", str(strategy_id))

    repo = SubscriptionRepository(session)
    return await repo.create(data)


async def get_subscription(
    session: AsyncSession,
    id: uuid.UUID,
) -> Subscription:
    """Return a subscription by id. Raises NotFoundError if not found."""
    repo = SubscriptionRepository(session)
    subscription = await repo.get_by_id(id)
    if subscription is None:
        raise NotFoundError("Subscription", str(id))
    return subscription


async def list_subscriptions(
    session: AsyncSession,
    channel_id: uuid.UUID | None = None,
    strategy_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Subscription], int]:
    """Return (items, total_count) with optional filters."""
    repo = SubscriptionRepository(session)

    filters: dict[str, Any] = {}
    if channel_id is not None:
        filters["channel_id"] = channel_id
    if strategy_id is not None:
        filters["strategy_id"] = strategy_id
    if is_active is not None:
        filters["is_active"] = is_active

    items = await repo.list(skip=offset, limit=limit, **filters)
    total = await repo.count(**filters)
    return items, total


async def update_subscription(
    session: AsyncSession,
    id: uuid.UUID,
    data: dict[str, Any],
) -> Subscription:
    """Update a subscription. Validates referenced channel/strategy if changed."""
    repo = SubscriptionRepository(session)
    subscription = await repo.get_by_id(id)
    if subscription is None:
        raise NotFoundError("Subscription", str(id))

    if "channel_id" in data:
        channel_repo = ChannelRepository(session)
        channel = await channel_repo.get_by_id(data["channel_id"])
        if channel is None:
            raise NotFoundError("Channel", str(data["channel_id"]))

    if "strategy_id" in data and data["strategy_id"] is not None:
        strategy_repo = StrategyRepository(session)
        strategy = await strategy_repo.get_by_id(data["strategy_id"])
        if strategy is None:
            raise NotFoundError("Strategy", str(data["strategy_id"]))

    updated = await repo.update(id, data)
    if updated is None:
        raise NotFoundError("Subscription", str(id))
    return updated


async def delete_subscription(session: AsyncSession, id: uuid.UUID) -> None:
    """Hard-delete a subscription."""
    repo = SubscriptionRepository(session)
    subscription = await repo.get_by_id(id)
    if subscription is None:
        raise NotFoundError("Subscription", str(id))
    await repo.delete(id)
