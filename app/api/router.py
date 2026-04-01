import structlog
from fastapi import APIRouter
from fastapi.responses import ORJSONResponse
from sqlalchemy import text

from app.api.v1 import admin, backtests, channels, outcomes, signals, strategies, subscriptions
from app.config import get_settings
from app.db.redis import get_redis
from app.db.session import get_engine
from app.schemas.common import HealthResponse

logger = structlog.get_logger(__name__)

api_router = APIRouter()

# Health endpoints (public)
@api_router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        environment=settings.environment,
    )


@api_router.get("/health/ready", tags=["Health"])
async def readiness():
    results = {}
    status_code = 200

    # Check DB
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        results["db"] = "ok"
    except Exception as e:
        logger.error("DB health check failed", error=str(e))
        results["db"] = "error"
        status_code = 503

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        results["redis"] = "ok"
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        results["redis"] = "error"
        status_code = 503

    return ORJSONResponse(content=results, status_code=status_code)


# v1 routers
api_router.include_router(signals.router, prefix="/api/v1", tags=["Signals"])
api_router.include_router(strategies.router, prefix="/api/v1", tags=["Strategies"])
api_router.include_router(backtests.router, prefix="/api/v1", tags=["Backtests"])
api_router.include_router(channels.router, prefix="/api/v1", tags=["Channels"])
api_router.include_router(subscriptions.router, prefix="/api/v1", tags=["Subscriptions"])
api_router.include_router(outcomes.router, prefix="/api/v1", tags=["Outcomes"])
api_router.include_router(admin.router, prefix="/api/v1", tags=["Admin"])
