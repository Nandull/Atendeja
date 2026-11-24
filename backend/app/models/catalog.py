import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Service(TimestampMixin, Base):
    """Item do catálogo: nome, duração e preço."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    # Intervalo após o atendimento (limpeza da sala, preparo do equipamento).
    buffer_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    online_booking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProfessionalService(Base):
    """Quem faz qual serviço (e, opcionalmente, por outro preço)."""

    __tablename__ = "professional_services"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
        ForeignKeyConstraint(["tenant_id", "service_id"], ["services.tenant_id", "services.id"]),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    professional_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    service_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    price_cents_override: Mapped[int | None] = mapped_column(Integer)

    service: Mapped[Service] = relationship(lazy="joined")


class WorkingHour(Base):
    __tablename__ = "working_hours"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    professional_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0 = segunda
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class Professional(TimestampMixin, Base):
    __tablename__ = "professionals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    # Preenchido quando o profissional também faz login no sistema.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(120))
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    services: Mapped[list[ProfessionalService]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    working_hours: Mapped[list[WorkingHour]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by=(WorkingHour.weekday, WorkingHour.start_time),
    )


class TimeBlock(TimestampMixin, Base):
    """Período indisponível: folga, férias, feriado, manutenção."""

    __tablename__ = "time_blocks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    professional_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # nulo = todos
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    search_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(11), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    birth_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(40))
    marketing_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
