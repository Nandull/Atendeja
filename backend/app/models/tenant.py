import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Tenant(TimestampMixin, Base):
    """O estabelecimento. Cada um enxerga apenas os próprios dados (RLS)."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    niche: Mapped[str] = mapped_column(String(40), nullable=False, default="estetica")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Sao_Paulo")
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="trial")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Agendamento online (página pública /slug).
    booking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    booking_min_notice_min: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    booking_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    booking_note: Mapped[str | None] = mapped_column(String(500))
