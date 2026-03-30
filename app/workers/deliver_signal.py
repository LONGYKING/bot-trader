"""
deliver_signal arq job.

Fan-out: for each pending SignalDelivery for this signal,
load the channel, format the message, send it.
"""
import uuid

import structlog

from app.channels.registry import ChannelRegistry
from app.core.circuit_breaker import CircuitBreaker
from app.formatters.registry import get_formatter
from app.repositories.channel import ChannelRepository
from app.repositories.delivery import DeliveryRepository
from app.repositories.signal import SignalRepository

logger = structlog.get_logger(__name__)


async def deliver_signal(ctx: dict, signal_id: str) -> dict:
    """Fan-out delivery job for a single signal.

    ctx["session_factory"] is an async_sessionmaker set in on_startup.

    Steps:
        1. Load all SignalDelivery records for signal_id with status='pending'
        2. Load the Signal record
        3. For each delivery:
           a. Load Channel (with decrypted config)
           b. Get formatter for channel_type
           c. Format signal -> channel-native message
           d. Instantiate channel and call send(message)
           e. Update delivery: mark_sent or mark_failed
           f. On failure: enqueue retry_delivery job
        4. Return {"delivered": n, "failed": m}
    """
    log = logger.bind(signal_id=signal_id)
    log.info("deliver_signal.start")

    delivered = 0
    failed = 0

    # Grab Redis from ctx for circuit breaker usage
    redis = ctx.get("redis")

    async with ctx["session_factory"]() as session:
        async with session.begin():
            signal_repo = SignalRepository(session)
            signal_uuid = uuid.UUID(signal_id)
            signal = await signal_repo.get_by_id(signal_uuid)

            if signal is None:
                log.warning("deliver_signal.signal_not_found")
                return {"delivered": 0, "failed": 0}

            delivery_repo = DeliveryRepository(session)
            deliveries = await delivery_repo.get_by_signal(signal_uuid)

            # Filter to pending only
            pending_deliveries = [d for d in deliveries if d.status == "pending"]

            if not pending_deliveries:
                log.info("deliver_signal.no_pending_deliveries")
                return {"delivered": 0, "failed": 0}

            # Build signal_data dict for formatters
            signal_data = {
                "asset": signal.asset,
                "signal_value": signal.signal_value,
                "direction": signal.direction,
                "tenor_days": signal.tenor_days,
                "confidence": float(signal.confidence) if signal.confidence else None,
                "regime": signal.regime,
                "entry_price": float(signal.entry_price) if signal.entry_price else None,
                "rule_triggered": signal.rule_triggered,
                "indicator_snapshot": signal.indicator_snapshot or {},
            }

            channel_repo = ChannelRepository(session)

            for delivery in pending_deliveries:
                delivery_log = log.bind(
                    delivery_id=str(delivery.id), channel_id=str(delivery.channel_id)
                )

                # Circuit breaker check
                cb = CircuitBreaker(redis, str(delivery.channel_id)) if redis else None

                if cb and await cb.is_open():
                    delivery_log.warning("deliver_signal.circuit_breaker_open")
                    await delivery_repo.mark_failed(delivery.id, "Circuit breaker OPEN")
                    failed += 1
                    continue

                try:
                    # Load the channel with decrypted config
                    channel = await channel_repo.get_by_id(delivery.channel_id)
                    if channel is None:
                        raise ValueError(f"Channel {delivery.channel_id} not found")

                    # Get formatter for channel type
                    formatter = get_formatter(channel.channel_type)

                    # Format signal into channel-native message
                    formatted_message = formatter.format_signal(signal_data)

                    # Instantiate channel and send
                    channel_instance = ChannelRegistry.instantiate(
                        channel.channel_type, channel.config
                    )
                    result = await channel_instance.send(formatted_message)

                    if result.success:
                        if cb:
                            await cb.record_success()
                        await delivery_repo.mark_sent(
                            delivery.id, external_msg_id=result.external_msg_id
                        )
                        delivered += 1
                        delivery_log.info(
                            "deliver_signal.sent", external_msg_id=result.external_msg_id
                        )
                    else:
                        error_msg = result.error or "Unknown send failure"
                        if cb:
                            await cb.record_failure()
                        await delivery_repo.mark_failed(delivery.id, error=error_msg)
                        failed += 1
                        delivery_log.warning("deliver_signal.send_failed", error=error_msg)

                        # Enqueue retry
                        await ctx["redis"].enqueue_job(
                            "retry_delivery",
                            delivery_id=str(delivery.id),
                            attempt=1,
                        )

                except Exception as exc:  # noqa: BLE001
                    error_msg = str(exc)
                    delivery_log.exception("deliver_signal.exception", error=error_msg)
                    if cb:
                        await cb.record_failure()
                    try:
                        await delivery_repo.mark_failed(delivery.id, error=error_msg)
                    except Exception:  # noqa: BLE001
                        delivery_log.exception("deliver_signal.mark_failed_error")
                    failed += 1

                    # Enqueue retry for unexpected exceptions too
                    try:
                        await ctx["redis"].enqueue_job(
                            "retry_delivery",
                            delivery_id=str(delivery.id),
                            attempt=1,
                        )
                    except Exception:  # noqa: BLE001
                        delivery_log.exception("deliver_signal.enqueue_retry_error")

    log.info("deliver_signal.complete", delivered=delivered, failed=failed)
    return {"delivered": delivered, "failed": failed}
