from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime

import httpx

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

_BASE_URL = "https://api.lemonsqueezy.com/v1"

_EVENT_MAP: dict[str, NormalizedEventType] = {
    "order_created": NormalizedEventType.CHECKOUT_COMPLETED,
    "subscription_created": NormalizedEventType.SUBSCRIPTION_CREATED,
    "subscription_updated": NormalizedEventType.SUBSCRIPTION_UPDATED,
    "subscription_cancelled": NormalizedEventType.SUBSCRIPTION_CANCELLED,
    "subscription_expired": NormalizedEventType.SUBSCRIPTION_CANCELLED,
    "subscription_payment_failed": NormalizedEventType.PAYMENT_FAILED,
    "subscription_payment_success": NormalizedEventType.PAYMENT_SUCCEEDED,
}


@PaymentAdapterRegistry.register("lemonsqueezy")
class LemonSqueezyAdapter(AbstractPaymentAdapter):
    provider = "lemonsqueezy"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._api_key: str = config["api_key"]
        self._webhook_secret: str | None = config.get("webhook_secret")
        self._store_id: str | None = config.get("store_id")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
        }

    async def create_customer(self, email: str, name: str | None, metadata: dict[str, str]) -> str:
        # Lemon Squeezy creates customers implicitly on checkout; we return email as identifier
        # For consistency, we return the email — webhook will link order to this value
        return email

    async def create_checkout(
        self,
        plan_key: str,
        provider_price_id: str,  # variant_id in LS terminology
        provider_customer_id: str | None,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
    ) -> CheckoutResult:
        payload = {
            "data": {
                "type": "checkouts",
                "attributes": {
                    "checkout_options": {
                        "success_url": success_url,
                        "cancel_url": cancel_url,
                    },
                    "checkout_data": {
                        "custom": metadata,
                    },
                },
                "relationships": {
                    "store": {"data": {"type": "stores", "id": self._store_id}},
                    "variant": {"data": {"type": "variants", "id": provider_price_id}},
                },
            }
        }
        if provider_customer_id:
            payload["data"]["attributes"]["checkout_data"]["email"] = provider_customer_id

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE_URL}/checkouts",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            checkout_url = data["attributes"].get("url", "")
            return CheckoutResult(url=checkout_url, provider_session_id=data["id"])

    async def create_customer_portal(
        self,
        provider_customer_id: str,
        return_url: str,
    ) -> PortalResult:
        # Lemon Squeezy provides a customer portal URL per subscription
        # Return the LS dashboard URL; deep-links per subscription via subscription portal
        portal_url = f"https://app.lemonsqueezy.com/my-orders"
        return PortalResult(url=portal_url)

    async def parse_webhook(
        self,
        raw_body: bytes,
        signature_header: str | None,
        plan_price_map: dict[str, str],
    ) -> WebhookEvent | None:
        if self._webhook_secret and signature_header:
            expected = hmac.new(
                self._webhook_secret.encode(),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature_header):
                raise AuthenticationError("Invalid Lemon Squeezy webhook signature")

        payload = json.loads(raw_body)
        event_name: str = payload.get("meta", {}).get("event_name", "")
        event_type = _EVENT_MAP.get(event_name)
        if not event_type:
            return None

        data = payload.get("data", {})
        attributes = data.get("attributes", {})

        # Customer identifier — LS uses email as primary customer reference
        customer_email: str = attributes.get("user_email", "")
        subscription_id: str | None = str(data.get("id")) if "subscription" in event_name else None

        # Resolve variant → plan key
        variant_id: str | None = str(attributes.get("variant_id", "")) or None

        return WebhookEvent(
            provider="lemonsqueezy",
            event_type=event_type,
            provider_customer_id=customer_email,
            provider_subscription_id=subscription_id,
            plan_key=plan_price_map.get(variant_id) if variant_id else None,
            raw=payload,
        )

    async def cancel_subscription(self, provider_subscription_id: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{_BASE_URL}/subscriptions/{provider_subscription_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()

    async def get_subscription(self, provider_subscription_id: str) -> SubscriptionInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BASE_URL}/subscriptions/{provider_subscription_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()["data"]

        attributes = data["attributes"]
        variant_id = str(attributes.get("variant_id", ""))

        period_end: datetime | None = None
        end_str = attributes.get("renews_at") or attributes.get("ends_at")
        if end_str:
            period_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        return SubscriptionInfo(
            provider_subscription_id=data["id"],
            provider_customer_id=attributes.get("user_email", ""),
            status=attributes.get("status", "unknown"),
            plan_key=None,  # caller resolves via plan_price_map
            current_period_end=period_end,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_BASE_URL}/stores",
                    headers=self._headers(),
                )
                return resp.status_code == 200
        except Exception:
            return False
