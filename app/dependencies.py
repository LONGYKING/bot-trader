from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.exceptions import AuthenticationError, AuthorizationError
from app.models.api_key import ApiKey
from app.services import api_key_service

# ---------------------------------------------------------------------------
# Reusable type aliases
# ---------------------------------------------------------------------------

DBSession = Annotated[AsyncSession, Depends(get_db)]
"""Inject an async DB session. Use as a route parameter type instead of
``Annotated[AsyncSession, Depends(get_db)]``."""

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
"""Registers ``X-API-Key`` as an apiKey security scheme in the OpenAPI spec,
enabling the global Authorize button in Swagger UI."""


async def get_current_api_key(
    session: DBSession,
    x_api_key: Annotated[str | None, Security(_api_key_scheme)] = None,
) -> ApiKey:
    """FastAPI dependency: validates X-API-Key header, returns ApiKey model."""
    if not x_api_key:
        raise AuthenticationError()
    return await api_key_service.authenticate(session, x_api_key)


def require_scope(scope: str):
    """
    Dependency factory. Usage: Depends(require_scope("write:signals"))
    The "*" scope grants all permissions.
    """
    async def _check_scope(
        api_key: ApiKey = Depends(get_current_api_key),
    ) -> ApiKey:
        if "*" not in api_key.scopes and scope not in api_key.scopes:
            raise AuthorizationError(scope)
        return api_key
    return _check_scope


class PaginationParams:
    def __init__(self, page: int = 1, page_size: int = 50) -> None:
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 200)
        self.skip = (self.page - 1) * self.page_size
        self.limit = self.page_size
