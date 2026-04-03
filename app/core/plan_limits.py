from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import PlanFeatureError, PlanLimitError


@dataclass
class EffectiveLimits:
    """
    Resolved limits for a tenant — plan defaults merged with any per-tenant override.
    -1 means unlimited. 0 means the feature is fully disabled.
    None on allowlists means all values are allowed.
    """

    max_strategies: int
    max_channels: int
    max_api_keys: int
    max_backtests_per_month: int
    max_signals_per_day: int
    max_signals_per_month: int
    allowed_strategy_classes: list[str] | None   # None = all classes allowed
    allowed_channel_types: list[str] | None      # None = all types allowed
    can_backtest: bool
    can_create_api_keys: bool
    can_use_exchange_channels: bool

    # ── Enforcement helpers ───────────────────────────────────────────────────

    def check_strategy_class(self, strategy_class: str) -> None:
        if self.allowed_strategy_classes and strategy_class not in self.allowed_strategy_classes:
            raise PlanFeatureError(
                f"Strategy class '{strategy_class}' is not available on your current plan."
            )

    def check_channel_type(self, channel_type: str) -> None:
        if self.allowed_channel_types and channel_type not in self.allowed_channel_types:
            raise PlanFeatureError(
                f"Channel type '{channel_type}' is not available on your current plan."
            )

    def check_capacity(self, resource: str, current: int) -> None:
        """
        Raise PlanLimitError if the tenant is at or over the limit for `resource`.
        `resource` must match the `max_<resource>` field name (e.g. "strategies").
        """
        limit: int = getattr(self, f"max_{resource}")
        if limit != -1 and current >= limit:
            raise PlanLimitError(resource, current, limit)

    def check_feature(self, feature: str) -> None:
        """
        Raise PlanFeatureError if a boolean feature flag is False.
        `feature` must match a `can_<feature>` field (e.g. "backtest").
        """
        if not getattr(self, f"can_{feature}"):
            raise PlanFeatureError(
                f"Feature '{feature}' is not available on your current plan. Please upgrade."
            )


async def get_effective_limits(session: AsyncSession, tenant: object) -> EffectiveLimits:
    """
    Single source of truth for what a tenant can do.

    Reads the tenant's Plan from the DB, then applies any TenantOverride field-by-field.
    Override fields that are None inherit from the plan — no code change needed to adjust limits.
    """
    from app.repositories.plan import OverrideRepository, PlanRepository

    plan_repo = PlanRepository(session)
    override_repo = OverrideRepository(session)

    plan = await plan_repo.get_by_key(tenant.plan_key)  # type: ignore[attr-defined]
    if plan is None:
        raise ValueError(f"Plan '{tenant.plan_key}' not found in database")  # type: ignore[attr-defined]

    override = await override_repo.get_by_tenant(tenant.id)  # type: ignore[attr-defined]

    def resolve(field: str):
        if override is not None:
            value = getattr(override, field, None)
            if value is not None:
                return value
        return getattr(plan, field)

    return EffectiveLimits(
        max_strategies=resolve("max_strategies"),
        max_channels=resolve("max_channels"),
        max_api_keys=resolve("max_api_keys"),
        max_backtests_per_month=resolve("max_backtests_per_month"),
        max_signals_per_day=resolve("max_signals_per_day"),
        max_signals_per_month=resolve("max_signals_per_month"),
        allowed_strategy_classes=resolve("allowed_strategy_classes"),
        allowed_channel_types=resolve("allowed_channel_types"),
        can_backtest=resolve("can_backtest"),
        can_create_api_keys=resolve("can_create_api_keys"),
        can_use_exchange_channels=resolve("can_use_exchange_channels"),
    )
