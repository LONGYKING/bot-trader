from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

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

_EVENT_MAP: dict[str, NormalizedEventType] = {
    "transaction.completed": NormalizedEventType.CHECKOUT_COMPLETED,
    "subscription.created": NormalizedEventType.SUBSCRIPTION_CREATED,
    "subscription.updated": NormalizedEventType.SUBSCRIPTION_UPDATED,
    "subscription.cancelled": NormalizedEventType.SUBSCRIPTION_CANCELLED,
    "subscription.past_due": NormalizedEventType.PAYMENT_FAILED,
    "transaction.payment_failed": NormalizedEventType.PAYMENT_FAILED,
    "subscription.activated": NormalizedEventType.PAYMENT_SUCCEEDED,
}

_SANDBOX_BASE = "https://sandbox-api.paddle.com"
_PRODUCTION_BASE = "https://api.paddle.com"


@PaymentAdapterRegistry.register("paddle")
class PaddleAdapter(AbstractPaymentAdapter):
    provider = "paddle"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._api_key: str = config["api_key"]
        self._webhook_secret: str | None = config.get("webhook_secret")
        self._base_url = (
            _PRODUCTION_BASE if config.get("environment") == "production" else _SANDBOX_BASE
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def create_customer(self, email: str, name: str | None, metadata: dict[str, str]) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/customers",
                headers=self._headers(),
                json={"email": email, "name": name, "custom_data": metadata},
            )
            resp.raise_for_status()
            return resp.json()["data"]["id"]

    async def create_checkout(
        self,
        plan_key: str,
        provider_price_id: str,
        provider_customer_id: str | None,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
    ) -> CheckoutResult:
        payload: dict = {
            "items": [{"price_id": provider_price_id, "quantity": 1}],
            "success_url": success_url,
            "custom_data": metadata,
        }
        if provider_customer_id:
            payload["customer_id"] = provider_customer_id

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/transactions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            checkout_url = data.get("checkout", {}).get("url", "")
            return CheckoutResult(url=checkout_url, provider_session_id=data["id"])

    async def create_customer_portal(
        self,
        provider_customer_id: str,
        return_url: str,
    ) -> PortalResult:
        # Paddle uses a static portal URL — customers manage subscriptions there directly
        portal_url = f"{self._base_url.replace('api.', 'customer.')}/portal"
        return PortalResult(url=portal_url)

    async def parse_webhook(
        self,
        raw_body: bytes,
        signature_header: str | None,
        plan_price_map: dict[str, str],
    ) -> WebhookEvent | None:
        if self._webhook_secret and signature_header:
            # Paddle uses h1=<ts>;<signature> format
            try:
                ts_part, sig_part = signature_header.split(";", 1)
                ts = ts_part.split("=", 1)[1]
                signed_payload = f"{ts}:{raw_body.decode()}"
                expected = hmac.new(
                    self._webhook_secret.encode(),
                    signed_payload.encode(),
                    hashlib.sha256,
                ).hexdigest()
                received = sig_part.split("=", 1)[1]
                if not hmac.compare_digest(expected, received):
                    raise AuthenticationError("Invalid Paddle webhook signature")
            except (ValueError, KeyError):
                raise AuthenticationError("Malformed Paddle webhook signature")

        payload = json.loads(raw_body)
        event_type_str: str = payload.get("event_type", "")
        event_type = _EVENT_MAP.get(event_type_str)
        if not event_type:
            return None

        data = payload.get("data", {})
        customer_id: str = data.get("customer_id", "")
        subscription_id: str | None = data.get("subscription_id") or (
            data.get("id") if "subscription" in event_type_str else None
        )

        # Resolve price → plan key
        price_id: str | None = None
        items = data.get("items", [])
        if items:
            price_id = items[0].get("price", {}).get("id")

        return WebhookEvent(
            provider="paddle",
            event_type=event_type,
            provider_customer_id=customer_id,
            provider_subscription_id=subscription_id,
            plan_key=plan_price_map.get(price_id) if price_id else None,
            raw=payload,
        )

    async def cancel_subscription(self, provider_subscription_id: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/subscriptions/{provider_subscription_id}/cancel",
                headers=self._headers(),
                json={"effective_from": "next_billing_period"},
            )
            resp.raise_for_status()

    async def get_subscription(self, provider_subscription_id: str) -> SubscriptionInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/subscriptions/{provider_subscription_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            sub = resp.json()["data"]

        price_id: str | None = None
        items = sub.get("items", [])
        if items:
            price_id = items[0].get("price", {}).get("id")

        period_end: datetime | None = None
        end_str = sub.get("current_billing_period", {}).get("ends_at")
        if end_str:
            period_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        return SubscriptionInfo(
            provider_subscription_id=sub["id"],
            provider_customer_id=sub.get("customer_id", ""),
            status=sub.get("status", "unknown"),
            plan_key=None,  # caller resolves via plan_price_map
            current_period_end=period_end,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/products",
                    headers=self._headers(),
                    params={"per_page": 1},
                )
                return resp.status_code == 200
        except Exception:
            return False
