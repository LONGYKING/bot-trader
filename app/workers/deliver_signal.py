"""
deliver_signal arq job.

Fan-out: for each pending SignalDelivery for this signal,
load the channel, format the message, and send it.
"""
import time
import uuid
from datetime import UTC, datetime

import structlog

from app.channels.registry import ChannelRegistry
from app.core.circuit_breaker import CircuitBreaker
from app.formatters.registry import get_formatter
from app.repositories.channel import ChannelRepository
from app.repositories.delivery import DeliveryRepository
from app.repositories.signal import SignalRepository
from app.repositories.subscription import SubscriptionRepository
from app.types.channel_config import _BaseChannelConfig, parse_channel_config
from app.types.delivery import DeliveryMetadata
from app.types.signal import SignalData
from app.types.subscription import SubscriptionPreferences

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _is_quiet_hour(prefs: SubscriptionPreferences) -> bool:
    """Return ``True`` if the current local time falls within the quiet window."""
    quiet = prefs.quiet_hours
    if quiet is None:
        return False
    try:
        from zoneinfo import ZoneInfo
        local_now = datetime.now(UTC).astimezone(ZoneInfo(quiet.timezone))
    except Exception:  # noqa: BLE001
        return False
    local_time = local_now.strftime("%H:%M")
    start, end = quiet.start, quiet.end
    if start <= end:
        return start <= local_time < end
    return local_time >= start or local_time < end  # overnight window


async def _is_rate_limited(redis: object, channel_id: uuid.UUID, limit: int) -> bool:
    """Increment the per-channel per-minute Redis counter atomically.

    Returns ``True`` (rate-limited) if the counter exceeds *limit*
    after incrementing. Pipeline ensures the TTL is always set.
    """
    minute_key = (
        f"signal:rate:{channel_id}:"
        f"{datetime.now(UTC).strftime('%Y%m%d%H%M')}"
    )
    pipe = redis.pipeline()  # type: ignore[attr-defined]
    pipe.incr(minute_key)
    pipe.expire(minute_key, 60)
    results = await pipe.execute()
    return results[0] > limit


async def _enqueue_retry(ctx: dict, delivery_id: uuid.UUID) -> None:
    """Enqueue a retry_delivery job, swallowing any enqueue error."""
    try:
        await ctx["redis"].enqueue_job(
            "retry_delivery",
            delivery_id=str(delivery_id),
            attempt=1,
        )
    except Exception:  # noqa: BLE001
        logger.exception("deliver_signal.enqueue_retry_error",
                         delivery_id=str(delivery_id))


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


async def deliver_signal(ctx: dict, signal_id: str) -> dict:
    """Fan-out delivery job for a single signal.

    ``ctx["session_factory"]`` is an ``async_sessionmaker`` set in on_startup.

    Steps:
        1. Load the ``Signal`` record.
        2. Load all ``SignalDelivery`` records with ``status='pending'``.
        3. For each delivery:
            a. Load ``Channel`` (with decrypted config).
            b. Circuit breaker check (per-channel config overrides).
            c. Channel-level filtering (Phase 1F).
            d. Subscription preferences (quiet hours, hourly throttle).
            e. Per-channel rate limiting.
            f. Format ``SignalData`` → channel-native message.
            g. Send and record latency in ``delivery_metadata``.
            h. Mark sent or failed; enqueue retry on failure.
        4. Return ``{"delivered": n, "failed": m}``.
    """
    log = logger.bind(signal_id=signal_id)
    log.info("deliver_signal.start")

    delivered = 0
    failed = 0
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
            pending = [d for d in deliveries if d.status == "pending"]

            if not pending:
                log.info("deliver_signal.no_pending_deliveries")
                return {"delivered": 0, "failed": 0}

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

            channel_repo = ChannelRepository(session)
            sub_repo = SubscriptionRepository(session)

            for delivery in pending:
                d_log = log.bind(
                    delivery_id=str(delivery.id),
                    channel_id=str(delivery.channel_id),
                )

                # Idempotency guard — re-fetch status to handle arq job replay
                fresh = await delivery_repo.get_by_id(delivery.id)
                if fresh is None or fresh.status != "pending":
                    d_log.debug(
                        "deliver_signal.skipped_not_pending",
                        status=getattr(fresh, "status", None),
                    )
                    continue

                # Load channel early — needed for CB config and rate limiting
                channel = await channel_repo.get_by_id(delivery.channel_id)
                if channel is None:
                    d_log.warning("deliver_signal.channel_not_found")
                    await delivery_repo.mark_failed(
                        delivery.id, f"Channel {delivery.channel_id} not found"
                    )
                    failed += 1
                    continue

                # Parse config into typed model (validates required fields)
                cfg = parse_channel_config(channel.channel_type, channel.config)

                # Circuit breaker (per-channel overrides via typed config)
                cb = CircuitBreaker(
                    redis,
                    str(delivery.channel_id),
                    failure_threshold=cfg.cb_failure_threshold,
                    recovery_timeout=cfg.cb_recovery_timeout,
                    window_seconds=cfg.cb_window_seconds,
                ) if redis else None

                if cb and await cb.is_open():
                    d_log.warning("deliver_signal.circuit_breaker_open")
                    await delivery_repo.mark_failed(delivery.id, "Circuit breaker OPEN")
                    failed += 1
                    continue

                try:
                    # --- Channel-level filtering (1F) ---
                    if channel.channel_type != "exchange":
                        skip = await _apply_notification_filters(
                            cfg, signal, delivery, delivery_repo, d_log
                        )
                        if skip:
                            failed += 1
                            continue

                    # --- Subscription preferences (1D) ---
                    subscription = await sub_repo.get_by_id(delivery.subscription_id)
                    if subscription:
                        prefs = SubscriptionPreferences.model_validate(
                            subscription.preferences or {}
                        )
                        skip = await _apply_subscription_preferences(
                            prefs, redis, delivery, delivery_repo, d_log
                        )
                        if skip:
                            failed += 1
                            continue

                    # --- Per-channel rate limiting (2B) ---
                    if cfg.rate_limit_per_minute and redis:
                        rate_limit = cfg.rate_limit_per_minute
                        limited = await _is_rate_limited(redis, delivery.channel_id, rate_limit)
                        if limited:
                            d_log.debug("deliver_signal.rate_limited",
                                        limit=cfg.rate_limit_per_minute)
                            await delivery_repo.mark_failed(
                                delivery.id, "Channel rate limit reached"
                            )
                            failed += 1
                            continue

                    # --- Format and send ---
                    formatter = get_formatter(channel.channel_type)
                    formatted_message = formatter.format_signal(signal_data)
                    channel_instance = ChannelRegistry.instantiate(
                        channel.channel_type, channel.config
                    )

                    t0 = time.monotonic()
                    result = await channel_instance.send(formatted_message)
                    latency_ms = int((time.monotonic() - t0) * 1000)

                    if result.success:
                        if cb:
                            await cb.record_success()
                        metadata = DeliveryMetadata(  # type: ignore[call-arg]
                            latency_ms=latency_ms,
                            channel_type=channel.channel_type,
                            formatter=type(formatter).__name__,
                        )
                        await delivery_repo.mark_sent(
                            delivery.id,
                            external_msg_id=result.external_msg_id,
                            delivery_metadata=metadata.model_dump(),
                        )
                        delivered += 1
                        d_log.info("deliver_signal.sent",
                                   external_msg_id=result.external_msg_id,
                                   latency_ms=latency_ms)
                    else:
                        error_msg = result.error or "Unknown send failure"
                        if cb:
                            await cb.record_failure()
                        await delivery_repo.mark_failed(delivery.id, error=error_msg)
                        failed += 1
                        d_log.warning("deliver_signal.send_failed", error=error_msg)
                        await _enqueue_retry(ctx, delivery.id)

                except Exception as exc:  # noqa: BLE001
                    error_msg = str(exc)
                    d_log.exception("deliver_signal.exception", error=error_msg)
                    if cb:
                        await cb.record_failure()
                    try:
                        await delivery_repo.mark_failed(delivery.id, error=error_msg)
                    except Exception:  # noqa: BLE001
                        d_log.exception("deliver_signal.mark_failed_error")
                    failed += 1
                    await _enqueue_retry(ctx, delivery.id)

    log.info("deliver_signal.complete", delivered=delivered, failed=failed)
    return {"delivered": delivered, "failed": failed}


# ---------------------------------------------------------------------------
# Filter helpers (extracted to keep the main loop readable)
# ---------------------------------------------------------------------------


async def _apply_notification_filters(
    cfg: _BaseChannelConfig,
    signal: object,
    delivery: object,
    delivery_repo: DeliveryRepository,
    d_log: object,
) -> bool:
    """Apply Phase-1F channel-level filters for notification channels.

    Returns ``True`` if delivery should be skipped (and the record has been
    marked failed), ``False`` to proceed.
    """
    from app.types.channel_config import NotificationChannelConfig

    if not isinstance(cfg, NotificationChannelConfig):
        return False

    if not cfg.notifications_enabled:
        d_log.debug("deliver_signal.notifications_disabled")  # type: ignore[attr-defined]
        await delivery_repo.mark_failed(delivery.id, "notifications_enabled=false")  # type: ignore[attr-defined]
        return True

    if cfg.min_signal_strength and abs(signal.signal_value) < cfg.min_signal_strength:  # type: ignore[attr-defined]
        d_log.debug("deliver_signal.signal_below_min_strength")  # type: ignore[attr-defined]
        await delivery_repo.mark_failed(delivery.id, "Signal below min_signal_strength")  # type: ignore[attr-defined]
        return True

    if cfg.trade_type_filter and signal.trade_type not in cfg.trade_type_filter:  # type: ignore[attr-defined]
        d_log.debug("deliver_signal.trade_type_filtered")  # type: ignore[attr-defined]
        await delivery_repo.mark_failed(delivery.id, "Signal trade_type filtered")  # type: ignore[attr-defined]
        return True

    if cfg.direction_filter and cfg.direction_filter != "both":
        is_long = signal.direction in ("long", "call")  # type: ignore[attr-defined]
        if cfg.direction_filter == "long_only" and not is_long:
            await delivery_repo.mark_failed(delivery.id, "direction_filter=long_only")  # type: ignore[attr-defined]
            return True
        if cfg.direction_filter == "short_only" and is_long:
            await delivery_repo.mark_failed(delivery.id, "direction_filter=short_only")  # type: ignore[attr-defined]
            return True

    return False


async def _apply_subscription_preferences(
    prefs: SubscriptionPreferences,
    redis: object,
    delivery: object,
    delivery_repo: DeliveryRepository,
    d_log: object,
) -> bool:
    """Apply Phase-1D subscription preferences (quiet hours, hourly throttle).

    Returns ``True`` if delivery should be skipped, ``False`` to proceed.
    """
    if _is_quiet_hour(prefs):
        d_log.debug("deliver_signal.quiet_hours")  # type: ignore[attr-defined]
        await delivery_repo.mark_failed(delivery.id, "Quiet hours")  # type: ignore[attr-defined]
        return True

    if prefs.max_signals_per_hour and redis:
        hour_key = (
            f"signal:sub_rate:{delivery.subscription_id}:"  # type: ignore[attr-defined]
            f"{datetime.now(UTC).strftime('%Y%m%d%H')}"
        )
        pipe = redis.pipeline()  # type: ignore[attr-defined]
        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)
        results = await pipe.execute()
        if results[0] > prefs.max_signals_per_hour:
            d_log.debug("deliver_signal.hourly_throttle")  # type: ignore[attr-defined]
            await delivery_repo.mark_failed(delivery.id, "Hourly signal limit reached")  # type: ignore[attr-defined]
            return True

    return False
