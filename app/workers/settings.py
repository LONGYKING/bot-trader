from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.workers.compute_outcomes import compute_outcomes
from app.workers.deliver_outcomes import deliver_outcomes
from app.workers.deliver_signal import deliver_signal
from app.workers.health_check_channels import health_check_channels
from app.workers.notify_neutral import notify_neutral
from app.workers.retry_delivery import retry_delivery
from app.workers.run_backtest import run_backtest
from app.workers.scheduled_signals import scheduled_signals


async def startup(ctx: dict) -> None:
    """Initialize shared resources for arq workers."""
    settings = get_settings()  # noqa: F841 — available for future ctx bindings
    engine = get_engine()
    ctx["engine"] = engine
    ctx["session_factory"] = get_session_factory()


async def shutdown(ctx: dict) -> None:
    """Cleanup arq worker resources."""
    if "engine" in ctx:
        await ctx["engine"].dispose()


class WorkerSettings:
    functions = [deliver_signal, retry_delivery, run_backtest, compute_outcomes, scheduled_signals, notify_neutral, deliver_outcomes, health_check_channels]
    cron_jobs = [
        cron(compute_outcomes, hour=2, minute=0),
        cron(scheduled_signals, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(health_check_channels, minute={0, 30}),
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_dsn)
    max_jobs = 20
    job_timeout = 600
    max_tries = 3
    on_startup = startup
    on_shutdown = shutdown
