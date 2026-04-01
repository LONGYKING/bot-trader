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

from app.config import get_settings


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

            s = get_settings()
            rate_limit = s.api_rate_limit_requests
            window_sec = s.api_rate_limit_window_seconds

            now = int(time.time())
            window_key = f"ratelimit:{api_key}:{now // window_sec}"

            pipe = redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, window_sec * 2)
            results = await pipe.execute()

            count = results[0]
            if count > rate_limit:
                return ORJSONResponse(
                    status_code=429,
                    content={"detail": f"Rate limit exceeded. Max {rate_limit} requests/minute."},
                    headers={"Retry-After": str(window_sec - (now % window_sec))},
                )
        except Exception:
            # If Redis is unavailable, allow the request through
            pass

        return await call_next(request)
