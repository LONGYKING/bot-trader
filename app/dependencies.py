from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.exceptions import AuthenticationError, AuthorizationError
from app.models.api_key import ApiKey
from app.models.tenant import Tenant
from app.services import api_key_service

# ---------------------------------------------------------------------------
# Reusable type aliases
# ---------------------------------------------------------------------------

DBSession = Annotated[AsyncSession, Depends(get_db)]
"""Inject an async DB session."""

# ---------------------------------------------------------------------------
# Auth schemes
# ---------------------------------------------------------------------------

_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# API key path (kept for backward compat / integrations)
# ---------------------------------------------------------------------------

async def get_current_api_key(
    session: DBSession,
    x_api_key: Annotated[str | None, Security(_api_key_scheme)] = None,
) -> ApiKey:
    """Validate X-API-Key header, return ApiKey model."""
    if not x_api_key:
        raise AuthenticationError()
    return await api_key_service.authenticate(session, x_api_key)


def require_scope(scope: str):
    """Legacy scope check for API key callers."""
    async def _check_scope(api_key: ApiKey = Depends(get_current_api_key)) -> ApiKey:
        if "*" not in api_key.scopes and scope not in api_key.scopes:
            raise AuthorizationError(scope)
        return api_key
    return _check_scope


# ---------------------------------------------------------------------------
# JWT path
# ---------------------------------------------------------------------------

async def _get_tenant_from_jwt(
    session: AsyncSession,
    credentials: HTTPAuthorizationCredentials,
) -> Tenant:
    from app.repositories.tenant import TenantRepository, UserRepository
    from app.services.auth_service import decode_token

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise AuthenticationError("Not an access token")

    tenant_id = uuid.UUID(payload["tenant_id"])
    tenant_repo = TenantRepository(session)
    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise AuthenticationError("Tenant not found")
    return tenant


# ---------------------------------------------------------------------------
# Unified auth context — accepts JWT Bearer OR X-API-Key
# ---------------------------------------------------------------------------

async def get_current_tenant(
    session: DBSession,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)] = None,
    x_api_key: Annotated[str | None, Security(_api_key_scheme)] = None,
) -> Tenant:
    """
    Unified dependency: returns the authenticated Tenant regardless of auth method.
    - JWT Bearer → validates token, resolves tenant_id from payload
    - X-API-Key → validates key, returns api_key.tenant (FK loaded)
    Raises AuthenticationError if neither is provided or valid.
    """
    if bearer:
        return await _get_tenant_from_jwt(session, bearer)

    if x_api_key:
        api_key = await api_key_service.authenticate(session, x_api_key)
        # Load tenant from api_key.tenant_id
        from app.repositories.tenant import TenantRepository
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_by_id(api_key.tenant_id)
        if not tenant:
            raise AuthenticationError("Tenant not found for API key")
        return tenant

    raise AuthenticationError("Authentication required: provide Bearer token or X-API-Key header")


CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
"""Inject the authenticated Tenant. Works with JWT or API key."""


# ---------------------------------------------------------------------------
# Admin guard — requires JWT and owner flag
# ---------------------------------------------------------------------------

async def require_owner(
    session: DBSession,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)] = None,
) -> Tenant:
    """Require JWT auth from an owner user. Used by admin routes."""
    if not bearer:
        raise AuthenticationError("Admin routes require JWT authentication")

    from app.repositories.tenant import UserRepository
    from app.services.auth_service import decode_token

    payload = decode_token(bearer.credentials)
    if payload.get("type") != "access":
        raise AuthenticationError("Not an access token")

    if not payload.get("is_owner"):
        raise AuthorizationError("owner")

    import uuid as _uuid
    tenant_id = _uuid.UUID(payload["tenant_id"])
    from app.repositories.tenant import TenantRepository
    tenant_repo = TenantRepository(session)
    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise AuthenticationError("Tenant not found")
    return tenant


AdminTenant = Annotated[Tenant, Depends(require_owner)]


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginationParams:
    def __init__(self, page: int = 1, page_size: int = 50) -> None:
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 200)
        self.skip = (self.page - 1) * self.page_size
        self.limit = self.page_size
