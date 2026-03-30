"""
compute_outcomes arq job — nightly cron at 02:00 UTC.

Delegates to outcome_service.resolve_outcomes to compute final P&L
for all expired, unresolved signals and persist SignalOutcome records.
After resolution, enqueues deliver_outcomes to notify subscribers.
"""
import structlog

from app.services import outcome_service

logger = structlog.get_logger(__name__)


async def compute_outcomes(ctx: dict) -> dict:
    """Resolve outcomes for all expired unresolved signals.

    ctx["session_factory"] is an async_sessionmaker set in on_startup.

    Delegates to outcome_service.resolve_outcomes(session).
    Returns {"resolved": count}.
    """
    log = logger.bind(job="compute_outcomes")
    log.info("compute_outcomes.start")

    try:
        async with ctx["session_factory"]() as session:
            async with session.begin():
                resolved_outcomes = await outcome_service.resolve_outcomes(session)

        count = len(resolved_outcomes)
        log.info("compute_outcomes.complete", resolved=count)

        # Fan out outcome notifications to subscribers in a separate job
        if resolved_outcomes:
            redis = ctx.get("redis")
            if redis:
                await redis.enqueue_job("deliver_outcomes", outcomes=resolved_outcomes)
                log.info("compute_outcomes.outcome_delivery_enqueued", count=count)

        return {"resolved": count}

    except Exception as exc:  # noqa: BLE001
        log.exception("compute_outcomes.failed", error=str(exc))
        return {"resolved": 0}
