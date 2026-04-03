from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from app.core.plan_limits import get_effective_limits
from app.dependencies import CurrentTenant, DBSession
from app.models.tenant import Tenant
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / Response schemas ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_owner: bool


class TenantOut(BaseModel):
    id: str
    name: str
    plan_key: str
    plan_status: str


class MeResponse(BaseModel):
    user: UserOut
    tenant: TenantOut
    limits: dict


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, session: DBSession) -> TokenResponse:
    access_token, refresh_token = await auth_service.register(
        session, data.email, data.password, data.full_name
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: DBSession) -> TokenResponse:
    access_token, refresh_token = await auth_service.login(session, data.email, data.password)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, session: DBSession) -> TokenResponse:
    access_token, refresh_token = await auth_service.refresh(session, data.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=204)
async def logout() -> None:
    # JWT is stateless — client drops the tokens.
    # Server-side revocation can be added via a Redis deny-list if needed.
    return None


@router.get("/me", response_model=MeResponse)
async def me(tenant: CurrentTenant, session: DBSession) -> MeResponse:
    from app.repositories.tenant import UserRepository

    user_repo = UserRepository(session)
    users = await user_repo.get_by_tenant(tenant.id)
    # Return the first owner (the authenticated user); for multi-user support
    # we'd extract user_id from the token — sufficient for single-owner workspaces now.
    owner = next((u for u in users if u.is_owner), users[0] if users else None)

    limits = await get_effective_limits(session, tenant)

    return MeResponse(
        user=UserOut(
            id=str(owner.id) if owner else "",
            email=owner.email if owner else "",
            full_name=owner.full_name if owner else None,
            is_owner=owner.is_owner if owner else False,
        ),
        tenant=TenantOut(
            id=str(tenant.id),
            name=tenant.name,
            plan_key=tenant.plan_key,
            plan_status=tenant.plan_status,
        ),
        limits={
            "max_strategies": limits.max_strategies,
            "max_channels": limits.max_channels,
            "max_api_keys": limits.max_api_keys,
            "max_backtests_per_month": limits.max_backtests_per_month,
            "max_signals_per_day": limits.max_signals_per_day,
            "max_signals_per_month": limits.max_signals_per_month,
            "allowed_strategy_classes": limits.allowed_strategy_classes,
            "allowed_channel_types": limits.allowed_channel_types,
            "can_backtest": limits.can_backtest,
            "can_create_api_keys": limits.can_create_api_keys,
            "can_use_exchange_channels": limits.can_use_exchange_channels,
        },
    )
