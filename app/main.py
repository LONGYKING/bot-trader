from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.middleware.auth import AuthMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.router import api_router
from app.config import get_settings
from app.db.redis import close_redis, get_redis
from app.db.session import get_engine
from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
    authentication_handler,
    authorization_handler,
    conflict_handler,
    external_service_handler,
    not_found_handler,
    validation_handler,
)
from app.logging import setup_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.environment)

    # Sentry init before anything else
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration(), SqlalchemyIntegration(), AsyncioIntegration()],
            traces_sample_rate=0.1,
            environment=settings.environment,
        )

    logger.info("Starting bot-trader signal platform", environment=settings.environment)

    # Warm up DB connection pool
    engine = get_engine()
    async with engine.connect():
        pass
    logger.info("Database connection pool initialized")

    # Initialise Redis and expose on app.state for middleware
    app.state.redis = None
    redis_pool = await get_redis()
    app.state.redis = redis_pool
    logger.info("Redis connection initialized")

    yield

    # Shutdown
    await engine.dispose()
    await close_redis()
    app.state.redis = None
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Bot Trader — Signal Platform",
        version="0.1.0",
        description="Cryptocurrency signal delivery platform",
        default_response_class=ORJSONResponse,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    # Prometheus metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (outermost first)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)

    # Exception handlers
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(ValidationError, validation_handler)
    app.add_exception_handler(AuthenticationError, authentication_handler)
    app.add_exception_handler(AuthorizationError, authorization_handler)
    app.add_exception_handler(ExternalServiceError, external_service_handler)

    # Routes
    app.include_router(api_router)

    return app


app = create_app()
