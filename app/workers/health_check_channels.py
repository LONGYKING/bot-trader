"""
health_check_channels arq cron job.

Runs every 30 minutes. Pings all active channels and updates
last_health_at / last_health_ok on the Channel record.

Consecutive failure tracking:
    Redis key: health:failures:{channel_id}  (int, expires after 2h)
    If count >= 3, a WARNING is logged with alert_needed=True so an
    external alerting hook (PagerDuty, Slack ops channel, etc.) can
    pick it up from the structured log stream.
"""
import structlog

from app.channels.registry import ChannelRegistry
from app.repositories.channel import ChannelRepository

logger = structlog.get_logger(__name__)

_CONSEC_FAILURE_THRESHOLD = 3
_FAILURE_KEY_TTL = 7200  # 2 hours


async def health_check_channels(ctx: dict) -> dict:
    """Ping every active channel and record health status."""
    log = logger.bind(job="health_check_channels")
    log.info("health_check_channels.start")

    redis = ctx.get("redis")
    ok_count = 0
    fail_count = 0

    async with ctx["session_factory"]() as session:
        async with session.begin():
            repo = ChannelRepository(session)
            channels = await repo.list_active()

            for channel in channels:
                ch_log = log.bind(channel_id=str(channel.id), channel_name=channel.name,
                                  channel_type=channel.channel_type)
                try:
                    instance = ChannelRegistry.instantiate(channel.channel_type, channel.config)
                    result = await instance.health_check()
                    is_ok = result.success
                except Exception as exc:  # noqa: BLE001
                    is_ok = False
                    ch_log.warning("health_check_channels.exception", error=str(exc))

                await repo.update_health(channel.id, ok=is_ok)

                failure_key = f"health:failures:{channel.id}"
                if is_ok:
                    ok_count += 1
                    if redis:
                        await redis.delete(failure_key)
                    ch_log.debug("health_check_channels.ok")
                else:
                    fail_count += 1
                    if redis:
                        consec = await redis.incr(failure_key)
                        await redis.expire(failure_key, _FAILURE_KEY_TTL)
                        if consec >= _CONSEC_FAILURE_THRESHOLD:
                            ch_log.warning(
                                "health_check_channels.consecutive_failures",
                                consecutive=consec,
                                alert_needed=True,
                            )
                        else:
                            ch_log.warning("health_check_channels.failed", consecutive=consec)
                    else:
                        ch_log.warning("health_check_channels.failed")

    log.info("health_check_channels.complete", ok=ok_count, failed=fail_count)
    return {"ok": ok_count, "failed": fail_count}
