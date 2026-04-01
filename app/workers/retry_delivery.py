"""
retry_delivery arq job with exponential backoff.

Re-attempts delivery for a single SignalDelivery record.
Backoff formula: min(2^attempt * 30, 960) seconds.
Max attempts: 5 — on exhaustion, moves to DLQ.
"""
import uuid
from datetime import timedelta

import structlog

from app.channels.registry import ChannelRegistry
from app.config import get_settings
from app.formatters.registry import get_formatter
from app.repositories.channel import ChannelRepository
from app.repositories.delivery import DeliveryRepository
from app.repositories.signal import SignalRepository
from app.types.channel_config import parse_channel_config
from app.types.signal import SignalData

logger = structlog.get_logger(__name__)


async def retry_delivery(ctx: dict, delivery_id: str, attempt: int) -> dict:
    """Retry a failed SignalDelivery with exponential backoff.

    ctx["session_factory"] is an async_sessionmaker set in on_startup.
    ctx["redis"] is the arq Redis pool.

    Steps:
        1. Load SignalDelivery by delivery_id
        2. If status == 'dlq' or attempt_count >= 5: skip (already in DLQ)
        3. Load Channel and Signal
        4. Attempt delivery again
        5. If success: mark_sent
        6. If failure and attempt < 5: mark_retrying + re-enqueue with
           delay = min(2^attempt * 30, 960) seconds
        7. If failure and attempt >= 5: mark_dlq
    """
    log = logger.bind(delivery_id=delivery_id, attempt=attempt)
    log.info("retry_delivery.start")

    async with ctx["session_factory"]() as session:
        async with session.begin():
            delivery_repo = DeliveryRepository(session)
            delivery_uuid = uuid.UUID(delivery_id)
            delivery = await delivery_repo.get_by_id(delivery_uuid)

            if delivery is None:
                log.warning("retry_delivery.delivery_not_found")
                return {"delivery_id": delivery_id, "attempt": attempt, "success": False}

            # Already in DLQ or exhausted — skip
            _max_attempts = get_settings().retry_max_attempts
            if delivery.status == "dlq" or delivery.attempt_count >= _max_attempts:
                log.info(
                    "retry_delivery.skipped",
                    status=delivery.status,
                    attempt_count=delivery.attempt_count,
                )
                return {"delivery_id": delivery_id, "attempt": attempt, "success": False}

            # Load channel and signal
            error_msg: str | None = None
            channel_repo = ChannelRepository(session)
            signal_repo = SignalRepository(session)

            channel = await channel_repo.get_by_id(delivery.channel_id)
            if channel is None:
                error_msg = f"Channel {delivery.channel_id} not found"
                log.warning("retry_delivery.channel_not_found")
                await delivery_repo.mark_dlq(delivery_uuid, error=error_msg)
                return {"delivery_id": delivery_id, "attempt": attempt, "success": False}

            signal = await signal_repo.get_by_id(delivery.signal_id)
            if signal is None:
                error_msg = f"Signal {delivery.signal_id} not found"
                log.warning("retry_delivery.signal_not_found")
                await delivery_repo.mark_dlq(delivery_uuid, error=error_msg)
                return {"delivery_id": delivery_id, "attempt": attempt, "success": False}

            signal_data = SignalData(
                asset=signal.asset,
                signal_value=signal.signal_value,
                trade_type=getattr(signal, "trade_type", "options") or "options",
                direction=signal.direction,
                tenor_days=signal.tenor_days,
                confidence=float(signal.confidence) if signal.confidence else None,
                regime=signal.regime,
                entry_price=float(signal.entry_price) if signal.entry_price else None,
                rule_triggered=signal.rule_triggered,
                indicator_snapshot=signal.indicator_snapshot or {},
            )

            success = False
            error_msg = None  # reset — early-return blocks above may have set this
            external_msg_id: str | None = None

            try:
                formatter = get_formatter(channel.channel_type)
                formatted_message = formatter.format_signal(signal_data)

                channel_instance = ChannelRegistry.instantiate(channel.channel_type, channel.config)
                result = await channel_instance.send(formatted_message)

                if result.success:
                    success = True
                    external_msg_id = result.external_msg_id
                else:
                    error_msg = result.error or "Unknown send failure"

            except Exception as exc:  # noqa: BLE001
                error_msg = str(exc)
                log.exception("retry_delivery.exception", error=error_msg)

            # Per-channel retry policy (falls back to global Settings)
            cfg = parse_channel_config(channel.channel_type, channel.config)
            s = get_settings()
            max_attempts = cfg.max_retries or s.retry_max_attempts
            backoff_base = cfg.backoff_base_seconds or s.retry_base_delay_seconds
            backoff_max = cfg.backoff_max_seconds or s.retry_max_delay_seconds

            if success:
                await delivery_repo.mark_sent(delivery_uuid, external_msg_id=external_msg_id)
                log.info("retry_delivery.success", external_msg_id=external_msg_id)
            elif attempt < max_attempts:
                # Mark as retrying and re-enqueue with exponential backoff
                await delivery_repo.mark_retrying(delivery_uuid, error=error_msg or "")
                delay_seconds = min((2 ** attempt) * backoff_base, backoff_max)
                log.warning(
                    "retry_delivery.retrying",
                    error=error_msg,
                    next_attempt=attempt + 1,
                    delay_seconds=delay_seconds,
                )
                await ctx["redis"].enqueue_job(
                    "retry_delivery",
                    delivery_id=delivery_id,
                    attempt=attempt + 1,
                    _defer_by=timedelta(seconds=delay_seconds),
                )
            else:
                # Exhausted all attempts — move to DLQ
                dlq_reason = error_msg or f"Max attempts ({max_attempts}) reached"
                await delivery_repo.mark_dlq(delivery_uuid, error=dlq_reason)
                log.error(
                    "retry_delivery.dlq",
                    error=error_msg,
                    attempt_count=delivery.attempt_count,
                )

    return {"delivery_id": delivery_id, "attempt": attempt, "success": success}
