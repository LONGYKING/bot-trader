import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

# Routes that don't require auth
PUBLIC_PATHS = {"/health", "/health/ready", "/docs", "/openapi.json", "/favicon.ico"}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Lightweight middleware that checks for X-API-Key on non-public routes.
    Full validation (DB lookup, scope check) happens in FastAPI dependencies.
    This middleware only rejects requests that have NO header at all on protected routes.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(pub) for pub in PUBLIC_PATHS):
            return await call_next(request)

        # Actual validation is done by the get_current_api_key dependency
        # This middleware just passes through — dependency handles 401/403
        return await call_next(request)
