import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Subscription(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    asset_filter: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    signal_filter: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger), nullable=True)
    min_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
