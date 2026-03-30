"""
Token bucket rate limiter middleware.
Rate: 60 requests/minute per API key.
Uses Redis with a sliding window counter.
"""
import time

from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

RATE_LIMIT = 60    # requests
WINDOW_SEC = 60    # seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health endpoints
        if request.url.path in ("/health", "/health/ready", "/metrics"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "anonymous")

        try:
            redis = request.app.state.redis
            if redis is None:
                return await call_next(request)

            now = int(time.time())
            window_key = f"ratelimit:{api_key}:{now // WINDOW_SEC}"

            pipe = redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, WINDOW_SEC * 2)
            results = await pipe.execute()

            count = results[0]
            if count > RATE_LIMIT:
                return ORJSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Max 60 requests/minute."},
                    headers={"Retry-After": str(WINDOW_SEC - (now % WINDOW_SEC))},
                )
        except Exception:
            # If Redis is unavailable, allow the request through
            pass

        return await call_next(request)
