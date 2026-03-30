"""
deliver_outcomes arq job.

After compute_outcomes resolves expired signals, this job notifies all
original subscribers with a trade-result message (win/loss, PnL, etc.).

Uses the existing signal_deliveries records (status='sent') to know which
channels received the original signal — those same channels get the outcome.
"""
import uuid

import structlog
from sqlalchemy import select

from app.channels.registry import ChannelRegistry
from app.formatters.registry import get_formatter
from app.models.delivery import SignalDelivery
from app.repositories.channel import ChannelRepository

logger = structlog.get_logger(__name__)


async def deliver_outcomes(ctx: dict, outcomes: list[dict]) -> dict:
    """Send outcome notifications for a batch of resolved signals.

    Each entry in *outcomes* must contain:
        signal_id, asset, direction, tenor_days,
        entry_price, exit_price, pnl_pct, is_profitable,
        entry_time, exit_time

    For each signal, finds the channels that received the original signal
    (deliveries with status='sent') and sends an outcome message.
    """
    log = logger.bind(job="deliver_outcomes", count=len(outcomes))
    log.info("deliver_outcomes.start")

    total_sent = 0
    total_failed = 0

    for outcome_data in outcomes:
        signal_id_str = outcome_data.get("signal_id")
        if not signal_id_str:
            continue

        signal_uuid = uuid.UUID(str(signal_id_str))

        async with ctx["session_factory"]() as session:
            async with session.begin():
                # Find all deliveries that were successfully sent for this signal
                stmt = (
                    select(SignalDelivery)
                    .where(
                        SignalDelivery.signal_id == signal_uuid,
                        SignalDelivery.status == "sent",
                    )
                )
                result = await session.execute(stmt)
                deliveries = list(result.scalars().all())

                if not deliveries:
                    continue

                # Deduplicate by channel_id
                channel_ids: set[uuid.UUID] = {d.channel_id for d in deliveries}

                channel_repo = ChannelRepository(session)

                for channel_id in channel_ids:
                    try:
                        channel = await channel_repo.get_by_id(channel_id)
                        if channel is None or not channel.is_active:
                            continue

                        formatter = get_formatter(channel.channel_type)
                        message = formatter.format_outcome(outcome_data)

                        channel_instance = ChannelRegistry.instantiate(channel.channel_type, channel.config)
                        delivery_result = await channel_instance.send(message)

                        if delivery_result.success:
                            total_sent += 1
                            log.debug(
                                "deliver_outcomes.sent",
                                signal_id=signal_id_str,
                                channel_id=str(channel_id),
                            )
                        else:
                            total_failed += 1
                            log.warning(
                                "deliver_outcomes.send_failed",
                                signal_id=signal_id_str,
                                channel_id=str(channel_id),
                                error=delivery_result.error,
                            )

                    except Exception as exc:  # noqa: BLE001
                        total_failed += 1
                        log.warning(
                            "deliver_outcomes.exception",
                            signal_id=signal_id_str,
                            channel_id=str(channel_id),
                            error=str(exc),
                        )

    log.info("deliver_outcomes.complete", sent=total_sent, failed=total_failed)
    return {"sent": total_sent, "failed": total_failed}
