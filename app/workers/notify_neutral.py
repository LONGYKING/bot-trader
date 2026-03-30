"""
notify_neutral arq job.

Broadcasts a lively market-scan update to all subscribers of a strategy
when the strategy runs but produces no actionable signal.

No signal is persisted — these are ephemeral "heartbeat" notifications
so subscribers feel the system is alive and watching.
"""
import uuid

import structlog
from sqlalchemy import and_, or_, select

from app.channels.registry import ChannelRegistry
from app.formatters.registry import get_formatter
from app.models.channel import Channel
from app.models.subscription import Subscription
from app.repositories.channel import ChannelRepository
from app.repositories.strategy import StrategyRepository

logger = structlog.get_logger(__name__)


async def notify_neutral(
    ctx: dict,
    strategy_id: str,
    asset: str,
    timeframe: str,
    current_price: float,
    regime: str | None = None,
    indicator_snapshot: dict | None = None,
) -> dict:
    """Send a neutral market-scan message to all subscribers of *strategy_id*.

    Finds all active (subscription, channel) pairs for the strategy and
    delivers a formatted neutral message directly — no delivery records created.
    """
    log = logger.bind(strategy_id=strategy_id, asset=asset)
    log.info("notify_neutral.start")

    strategy_uuid = uuid.UUID(strategy_id)
    sent = 0
    failed = 0

    async with ctx["session_factory"]() as session:
        async with session.begin():
            # Load strategy name for formatter context
            strategy_repo = StrategyRepository(session)
            strategy = await strategy_repo.get_by_id(strategy_uuid)
            strategy_name = strategy.name if strategy else asset

            # Find all active subscriptions for this strategy (or global ones)
            stmt = (
                select(Subscription, Channel)
                .join(Channel, Channel.id == Subscription.channel_id)
                .where(
                    and_(
                        Subscription.is_active == True,  # noqa: E712
                        Channel.is_active == True,  # noqa: E712
                        or_(
                            Subscription.strategy_id.is_(None),
                            Subscription.strategy_id == strategy_uuid,
                        ),
                    )
                )
            )
            result = await session.execute(stmt)
            pairs = list(result.all())

    if not pairs:
        log.info("notify_neutral.no_subscribers")
        return {"sent": 0, "failed": 0}

    neutral_data = {
        "asset": asset,
        "timeframe": timeframe,
        "current_price": current_price,
        "regime": regime,
        "indicator_snapshot": indicator_snapshot or {},
        "strategy_name": strategy_name,
    }

    # Deduplicate by channel_id (multiple subscriptions may share the same channel)
    seen_channels: set[uuid.UUID] = set()

    async with ctx["session_factory"]() as session:
        async with session.begin():
            channel_repo = ChannelRepository(session)

            for subscription, channel_row in pairs:
                if channel_row.id in seen_channels:
                    continue
                seen_channels.add(channel_row.id)

                try:
                    channel = await channel_repo.get_by_id(channel_row.id)
                    if channel is None:
                        continue

                    # Exchange channels execute orders — skip for neutral signals
                    if channel.channel_type == "exchange":
                        continue

                    formatter = get_formatter(channel.channel_type)
                    message = formatter.format_neutral(neutral_data)

                    channel_instance = ChannelRegistry.instantiate(channel.channel_type, channel.config)
                    delivery_result = await channel_instance.send(message)

                    if delivery_result.success:
                        sent += 1
                        log.debug("notify_neutral.sent", channel_id=str(channel.id))
                    else:
                        failed += 1
                        log.warning("notify_neutral.send_failed", channel_id=str(channel.id), error=delivery_result.error)

                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    log.warning("notify_neutral.exception", channel_id=str(channel_row.id), error=str(exc))

    log.info("notify_neutral.complete", sent=sent, failed=failed)
    return {"sent": sent, "failed": failed}
