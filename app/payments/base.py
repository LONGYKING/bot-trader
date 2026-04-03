from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class NormalizedEventType(str, Enum):
    CHECKOUT_COMPLETED = "checkout.completed"
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_SUCCEEDED = "payment.succeeded"


@dataclass
class WebhookEvent:
    """
    Normalised across all payment providers.
    The billing service only ever sees this — it has zero knowledge of which
    provider sent it.
    """

    provider: str
    event_type: NormalizedEventType
    provider_customer_id: str
    provider_subscription_id: str | None
    plan_key: str | None  # resolved by adapter from provider_price_ids lookup
    raw: dict[str, Any] = field(default_factory=dict)  # original payload for auditing


@dataclass
class CheckoutResult:
    url: str  # redirect the user here
    provider_session_id: str  # for logging/reference


@dataclass
class PortalResult:
    url: str


@dataclass
class SubscriptionInfo:
    provider_subscription_id: str
    provider_customer_id: str
    status: str  # "active" | "past_due" | "cancelled" | "trialing"
    plan_key: str | None
    current_period_end: datetime | None


class AbstractPaymentAdapter(ABC):
    """
    One implementation per payment provider. Each adapter handles all
    provider-specific API calls and webhook signature verification,
    then normalises the result into shared dataclasses.

    Adding a new provider = create one new file + register with
    @PaymentAdapterRegistry.register("<provider>").
    """

    provider: str  # class-level constant, e.g. "stripe"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    # ── Required abstract methods ─────────────────────────────────────────────

    @abstractmethod
    async def create_customer(
        self,
        email: str,
        name: str | None,
        metadata: dict[str, str],
    ) -> str:
        """Create a customer record in the provider. Returns provider_customer_id."""
        ...

    @abstractmethod
    async def create_checkout(
        self,
        plan_key: str,
        provider_price_id: str,
        provider_customer_id: str | None,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],  # always include {"tenant_id": "..."}
    ) -> CheckoutResult:
        ...

    @abstractmethod
    async def create_customer_portal(
        self,
        provider_customer_id: str,
        return_url: str,
    ) -> PortalResult:
        ...

    @abstractmethod
    async def parse_webhook(
        self,
        raw_body: bytes,
        signature_header: str | None,
        plan_price_map: dict[str, str],  # {provider_price_id → plan_key}
    ) -> WebhookEvent | None:
        """
        Verify webhook signature, parse the event, and normalise into WebhookEvent.
        Return None for unhandled event types — the billing service ignores them silently.
        Raise AuthenticationError if signature verification fails.
        """
        ...

    @abstractmethod
    async def cancel_subscription(self, provider_subscription_id: str) -> None:
        ...

    @abstractmethod
    async def get_subscription(self, provider_subscription_id: str) -> SubscriptionInfo:
        ...

    # ── Optional — override for richer behaviour ──────────────────────────────

    async def health_check(self) -> bool:
        """Ping the provider API. Default returns True (override to verify connectivity)."""
        return True
