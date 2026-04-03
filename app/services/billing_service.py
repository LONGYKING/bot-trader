from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Plan
from app.payments.base import NormalizedEventType, WebhookEvent
from app.repositories.plan import PlanRepository
from app.repositories.tenant import TenantRepository

logger = structlog.get_logger(__name__)


async def build_plan_price_map(session: AsyncSession, provider: str) -> dict[str, str]:
    """
    Build a { provider_price_id → plan_key } reverse lookup for webhook resolution.
    Reads all active plans from the DB — no hardcoded IDs.
    """
    repo = PlanRepository(session)
    plans: list[Plan] = await repo.list_all()
    result: dict[str, str] = {}
    for plan in plans:
        if plan.provider_price_ids:
            price_id = plan.provider_price_ids.get(provider)
            if price_id:
                result[price_id] = plan.key
    return result


async def handle_event(session: AsyncSession, event: WebhookEvent) -> None:
    """
    Provider-agnostic webhook handler. Only ever sees a normalised WebhookEvent.
    Has zero knowledge of which payment provider sent it.
    """
    tenant_repo = TenantRepository(session)

    tenant = await tenant_repo.get_by_provider_customer(
        event.provider, event.provider_customer_id
    )
    if not tenant:
        logger.warning(
            "webhook_tenant_not_found",
            provider=event.provider,
            provider_customer_id=event.provider_customer_id,
            event_type=event.event_type,
        )
        return

    match event.event_type:
        case NormalizedEventType.CHECKOUT_COMPLETED | NormalizedEventType.SUBSCRIPTION_CREATED:
            update_data: dict = {
                "plan_status": "active",
                "payment_provider": event.provider,
            }
            if event.plan_key:
                update_data["plan_key"] = event.plan_key
            if event.provider_subscription_id:
                update_data["provider_subscription_id"] = event.provider_subscription_id
            await tenant_repo.update(tenant.id, update_data)
            logger.info("billing_subscription_activated", tenant_id=str(tenant.id), plan_key=event.plan_key)

        case NormalizedEventType.SUBSCRIPTION_UPDATED:
            update_data = {"plan_status": "active"}
            if event.plan_key:
                update_data["plan_key"] = event.plan_key
            await tenant_repo.update(tenant.id, update_data)
            logger.info("billing_subscription_updated", tenant_id=str(tenant.id), plan_key=event.plan_key)

        case NormalizedEventType.SUBSCRIPTION_CANCELLED:
            await tenant_repo.update(
                tenant.id,
                {"plan_status": "cancelled", "plan_key": "free"},
            )
            logger.info("billing_subscription_cancelled", tenant_id=str(tenant.id))

        case NormalizedEventType.PAYMENT_FAILED:
            await tenant_repo.update(tenant.id, {"plan_status": "past_due"})
            logger.warning("billing_payment_failed", tenant_id=str(tenant.id))

        case NormalizedEventType.PAYMENT_SUCCEEDED:
            await tenant_repo.update(tenant.id, {"plan_status": "active"})
            logger.info("billing_payment_succeeded", tenant_id=str(tenant.id))

        case _:
            logger.debug("billing_event_unhandled", event_type=event.event_type)


async def create_checkout(
    session: AsyncSession,
    tenant_id_str: str,
    plan_key: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Return a checkout URL for the given tenant + plan."""
    from app.config import get_settings
    from app.payments import get_payment_adapter
    from app.repositories.plan import PlanRepository
    from app.repositories.tenant import TenantRepository

    settings = get_settings()
    plan_repo = PlanRepository(session)
    tenant_repo = TenantRepository(session)

    import uuid

    tenant = await tenant_repo.get_by_id(uuid.UUID(tenant_id_str))
    if not tenant:
        from app.exceptions import NotFoundError
        raise NotFoundError("Tenant", tenant_id_str)

    plan = await plan_repo.get_by_key(plan_key)
    if not plan:
        from app.exceptions import NotFoundError
        raise NotFoundError("Plan", plan_key)

    provider = settings.payment_provider
    price_id = (plan.provider_price_ids or {}).get(provider)
    if not price_id:
        raise ValueError(f"Plan '{plan_key}' has no price configured for provider '{provider}'")

    adapter = get_payment_adapter(provider)
    result = await adapter.create_checkout(
        plan_key=plan_key,
        provider_price_id=price_id,
        provider_customer_id=tenant.provider_customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"tenant_id": tenant_id_str, "plan_key": plan_key},
    )
    return result.url


async def create_portal(
    session: AsyncSession,
    tenant_id_str: str,
    return_url: str,
) -> str:
    """Return a billing portal URL for the given tenant."""
    from app.config import get_settings
    from app.payments import get_payment_adapter
    from app.repositories.tenant import TenantRepository

    import uuid

    settings = get_settings()
    tenant_repo = TenantRepository(session)

    tenant = await tenant_repo.get_by_id(uuid.UUID(tenant_id_str))
    if not tenant:
        from app.exceptions import NotFoundError
        raise NotFoundError("Tenant", tenant_id_str)

    if not tenant.provider_customer_id:
        raise ValueError("Tenant has no payment provider customer ID")

    provider = tenant.payment_provider or settings.payment_provider
    adapter = get_payment_adapter(provider)
    result = await adapter.create_customer_portal(
        provider_customer_id=tenant.provider_customer_id,
        return_url=return_url,
    )
    return result.url
