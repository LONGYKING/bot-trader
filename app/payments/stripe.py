from __future__ import annotations

from datetime import datetime, timezone

import stripe
from stripe import SignatureVerificationError as StripeSignatureVerificationError

from app.exceptions import AuthenticationError
from app.payments.base import (
    AbstractPaymentAdapter,
    CheckoutResult,
    NormalizedEventType,
    PortalResult,
    SubscriptionInfo,
    WebhookEvent,
)
from app.payments.registry import PaymentAdapterRegistry

_EVENT_MAP: dict[str, NormalizedEventType] = {
    "checkout.session.completed": NormalizedEventType.CHECKOUT_COMPLETED,
    "customer.subscription.created": NormalizedEventType.SUBSCRIPTION_CREATED,
    "customer.subscription.updated": NormalizedEventType.SUBSCRIPTION_UPDATED,
    "customer.subscription.deleted": NormalizedEventType.SUBSCRIPTION_CANCELLED,
    "invoice.payment_failed": NormalizedEventType.PAYMENT_FAILED,
    "invoice.payment_succeeded": NormalizedEventType.PAYMENT_SUCCEEDED,
}


@PaymentAdapterRegistry.register("stripe")
class StripeAdapter(AbstractPaymentAdapter):
    provider = "stripe"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        stripe.api_key = config["secret_key"]
        self._webhook_secret: str | None = config.get("webhook_secret")

    async def create_customer(self, email: str, name: str | None, metadata: dict[str, str]) -> str:
        customer = stripe.Customer.create(email=email, name=name, metadata=metadata)
        return customer.id

    async def create_checkout(
        self,
        plan_key: str,
        provider_price_id: str,
        provider_customer_id: str | None,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
    ) -> CheckoutResult:
        session = stripe.checkout.Session.create(
            customer=provider_customer_id,
            mode="subscription",
            line_items=[{"price": provider_price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )
        return CheckoutResult(url=session.url, provider_session_id=session.id)

    async def create_customer_portal(
        self,
        provider_customer_id: str,
        return_url: str,
    ) -> PortalResult:
        session = stripe.billing_portal.Session.create(
            customer=provider_customer_id,
            return_url=return_url,
        )
        return PortalResult(url=session.url)

    async def parse_webhook(
        self,
        raw_body: bytes,
        signature_header: str | None,
        plan_price_map: dict[str, str],
    ) -> WebhookEvent | None:
        try:
            event = stripe.Webhook.construct_event(
                raw_body, signature_header, self._webhook_secret
            )
        except StripeSignatureVerificationError:
            raise AuthenticationError("Invalid Stripe webhook signature")

        event_type = _EVENT_MAP.get(event["type"])
        if not event_type:
            return None  # unhandled — caller ignores silently

        obj = event["data"]["object"]

        # Resolve the price ID (varies by event type)
        price_id: str | None = None
        items = obj.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
        if not price_id:
            lines = obj.get("lines", {}).get("data", [])
            if lines:
                price_id = lines[0].get("price", {}).get("id")

        return WebhookEvent(
            provider="stripe",
            event_type=event_type,
            provider_customer_id=obj.get("customer", ""),
            provider_subscription_id=obj.get("subscription") or obj.get("id"),
            plan_key=plan_price_map.get(price_id) if price_id else None,
            raw=dict(event),
        )

    async def cancel_subscription(self, provider_subscription_id: str) -> None:
        stripe.Subscription.delete(provider_subscription_id)

    async def get_subscription(self, provider_subscription_id: str) -> SubscriptionInfo:
        sub = stripe.Subscription.retrieve(provider_subscription_id)
        price_id: str | None = None
        if sub["items"]["data"]:
            price_id = sub["items"]["data"][0]["price"]["id"]
        return SubscriptionInfo(
            provider_subscription_id=sub.id,
            provider_customer_id=sub.customer,
            status=sub.status,
            plan_key=None,  # caller resolves via plan_price_map
            current_period_end=datetime.fromtimestamp(
                sub.current_period_end, tz=timezone.utc
            ),
        )

    async def health_check(self) -> bool:
        try:
            stripe.Balance.retrieve()
            return True
        except Exception:
            return False
