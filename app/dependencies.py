from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.exceptions import AuthenticationError, AuthorizationError
from app.models.api_key import ApiKey
from app.services import api_key_service


async def get_current_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
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
