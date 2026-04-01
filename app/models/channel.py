from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Channel(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "channels"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)  # encrypted at rest
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    last_health_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
