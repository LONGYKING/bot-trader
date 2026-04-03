from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.dependencies import CurrentTenant, DBSession
from app.services import billing_service

router = APIRouter(prefix="/billing", tags=["billing"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan_key: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalRequest(BaseModel):
    return_url: str


class PortalResponse(BaseModel):
    portal_url: str


class BillingStatusResponse(BaseModel):
    plan_key: str
    plan_status: str
    payment_provider: str | None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/status", response_model=BillingStatusResponse)
async def billing_status(tenant: CurrentTenant) -> BillingStatusResponse:
    return BillingStatusResponse(
        plan_key=tenant.plan_key,
        plan_status=tenant.plan_status,
        payment_provider=tenant.payment_provider,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    data: CheckoutRequest,
    tenant: CurrentTenant,
    session: DBSession,
) -> CheckoutResponse:
    try:
        checkout_url = await billing_service.create_checkout(
            session=session,
            tenant_id_str=str(tenant.id),
            plan_key=data.plan_key,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    data: PortalRequest,
    tenant: CurrentTenant,
    session: DBSession,
) -> PortalResponse:
    try:
        portal_url = await billing_service.create_portal(
            session=session,
            tenant_id_str=str(tenant.id),
            return_url=data.return_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PortalResponse(portal_url=portal_url)


@router.post("/webhook/{provider}", include_in_schema=False, status_code=200)
async def handle_webhook(
    provider: str,
    request: Request,
    session: DBSession,
) -> dict:
    """
    Single parameterised webhook endpoint. Stripe → /billing/webhook/stripe, etc.
    No auth dependency — signature verification is done inside the adapter.
    """
    from app.payments import get_payment_adapter

    raw_body = await request.body()

    # Each provider uses a different signature header
    sig = (
        request.headers.get("stripe-signature")
        or request.headers.get("paddle-signature")
        or request.headers.get("x-signature")
    )

    adapter = get_payment_adapter(provider)
    plan_price_map = await billing_service.build_plan_price_map(session, provider)

    event = await adapter.parse_webhook(raw_body, sig, plan_price_map)
    if event is None:
        return {"status": "ignored"}

    await billing_service.handle_event(session, event)
    return {"status": "ok"}
