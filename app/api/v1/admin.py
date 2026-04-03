from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.dependencies import AdminTenant, DBSession, require_scope
from app.models.api_key import ApiKey
from app.repositories.api_key import ApiKeyRepository
from app.repositories.tenant import TenantRepository
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse, WorkerStats
from app.services import api_key_service, plan_service

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── API Key routes (unchanged) ────────────────────────────────────────────────

@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    repo = ApiKeyRepository(session)
    keys = await repo.list(limit=200)
    return keys


@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    api_key, raw_key = await api_key_service.create_api_key(
        session, body.name, body.scopes, body.expires_at
    )
    return ApiKeyCreatedResponse(**ApiKeyResponse.model_validate(api_key).model_dump(), raw_key=raw_key)


@router.delete("/api-keys/{id}", status_code=204)
async def revoke_api_key(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    await api_key_service.revoke_api_key(session, id)


@router.post("/api-keys/{id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_api_key(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    api_key, raw_key = await api_key_service.rotate_api_key(session, id)
    return ApiKeyCreatedResponse(**ApiKeyResponse.model_validate(api_key).model_dump(), raw_key=raw_key)


@router.get("/workers/stats", response_model=WorkerStats)
async def worker_stats(_: ApiKey = Depends(require_scope("admin"))):
    return WorkerStats(status="ok", message="Worker stats not yet implemented")


# ── Plan management ──────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans(
    _: AdminTenant,
    session: DBSession,
    public: bool = Query(False, description="Only return public-facing plans"),
) -> list[dict]:
    plans = await plan_service.list_plans(session, public_only=public)
    return [_plan_to_dict(p) for p in plans]


@router.post("/plans", status_code=201)
async def create_plan(
    body: dict[str, Any],
    _: AdminTenant,
    session: DBSession,
) -> dict:
    plan = await plan_service.create_plan(session, body)
    return _plan_to_dict(plan)


@router.patch("/plans/{key}")
async def update_plan(
    key: str,
    body: dict[str, Any],
    _: AdminTenant,
    session: DBSession,
) -> dict:
    plan = await plan_service.update_plan(session, key, body)
    return _plan_to_dict(plan)


@router.delete("/plans/{key}", status_code=204)
async def delete_plan(
    key: str,
    _: AdminTenant,
    session: DBSession,
) -> None:
    await plan_service.delete_plan(session, key)


# ── Tenant management ────────────────────────────────────────────────────────

@router.get("/tenants")
async def list_tenants(
    _: AdminTenant,
    session: DBSession,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    repo = TenantRepository(session)
    tenants = await repo.list(skip=skip, limit=limit)
    return [_tenant_to_dict(t) for t in tenants]


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: uuid.UUID,
    _: AdminTenant,
    session: DBSession,
) -> dict:
    repo = TenantRepository(session)
    tenant = await repo.get_by_id(tenant_id)
    if not tenant:
        from app.exceptions import NotFoundError
        raise NotFoundError("Tenant", str(tenant_id))
    return _tenant_to_dict(tenant)


@router.patch("/tenants/{tenant_id}/plan")
async def change_tenant_plan(
    tenant_id: uuid.UUID,
    body: dict[str, str],
    _: AdminTenant,
    session: DBSession,
) -> dict:
    repo = TenantRepository(session)
    tenant = await repo.update(tenant_id, {"plan_key": body["plan_key"]})
    if not tenant:
        from app.exceptions import NotFoundError
        raise NotFoundError("Tenant", str(tenant_id))
    return _tenant_to_dict(tenant)


@router.post("/tenants/{tenant_id}/override", status_code=200)
async def set_tenant_override(
    tenant_id: uuid.UUID,
    body: dict[str, Any],
    _: AdminTenant,
    session: DBSession,
) -> dict:
    override = await plan_service.set_tenant_override(session, tenant_id, body)
    return {
        "tenant_id": str(override.tenant_id),
        "notes": override.notes,
        "max_strategies": override.max_strategies,
        "max_channels": override.max_channels,
        "max_api_keys": override.max_api_keys,
        "max_backtests_per_month": override.max_backtests_per_month,
        "max_signals_per_day": override.max_signals_per_day,
        "max_signals_per_month": override.max_signals_per_month,
        "allowed_strategy_classes": override.allowed_strategy_classes,
        "allowed_channel_types": override.allowed_channel_types,
        "can_backtest": override.can_backtest,
        "can_create_api_keys": override.can_create_api_keys,
        "can_use_exchange_channels": override.can_use_exchange_channels,
    }


@router.delete("/tenants/{tenant_id}/override", status_code=204)
async def remove_tenant_override(
    tenant_id: uuid.UUID,
    _: AdminTenant,
    session: DBSession,
) -> None:
    await plan_service.remove_tenant_override(session, tenant_id)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _plan_to_dict(plan) -> dict:
    return {
        "key": plan.key,
        "display_name": plan.display_name,
        "description": plan.description,
        "price_monthly_cents": plan.price_monthly_cents,
        "provider_price_ids": plan.provider_price_ids,
        "is_active": plan.is_active,
        "is_public": plan.is_public,
        "sort_order": plan.sort_order,
        "max_strategies": plan.max_strategies,
        "max_channels": plan.max_channels,
        "max_api_keys": plan.max_api_keys,
        "max_backtests_per_month": plan.max_backtests_per_month,
        "max_signals_per_day": plan.max_signals_per_day,
        "max_signals_per_month": plan.max_signals_per_month,
        "allowed_strategy_classes": plan.allowed_strategy_classes,
        "allowed_channel_types": plan.allowed_channel_types,
        "can_backtest": plan.can_backtest,
        "can_create_api_keys": plan.can_create_api_keys,
        "can_use_exchange_channels": plan.can_use_exchange_channels,
    }


def _tenant_to_dict(tenant) -> dict:
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "plan_key": tenant.plan_key,
        "plan_status": tenant.plan_status,
        "payment_provider": tenant.payment_provider,
        "provider_customer_id": tenant.provider_customer_id,
        "provider_subscription_id": tenant.provider_subscription_id,
        "plan_expires_at": tenant.plan_expires_at.isoformat() if tenant.plan_expires_at else None,
        "created_at": tenant.created_at.isoformat() if hasattr(tenant, "created_at") else None,
    }
