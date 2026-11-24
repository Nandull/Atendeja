import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.catalog import Client, Professional, Service


class AppointmentStatus(enum.StrEnum):
    SCHEDULED = "scheduled"  # agendado
    CONFIRMED = "confirmed"  # confirmado pelo cliente
    COMPLETED = "completed"  # atendido
    CANCELED = "canceled"  # cancelado
    NO_SHOW = "no_show"  # cliente faltou


# Estados que ocupam a agenda (entram na trava de conflito).
OCCUPYING = {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED}
# Estados em que ainda dá para reagendar.
OPEN = {AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED}

# Transições permitidas. Concluído e falta podem ser corrigidos entre si
# (a recepção marcou errado); cancelado é definitivo.
TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.SCHEDULED: {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.CONFIRMED: {
        AppointmentStatus.SCHEDULED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.CANCELED,
        AppointmentStatus.NO_SHOW,
    },
    AppointmentStatus.COMPLETED: {AppointmentStatus.NO_SHOW},
    AppointmentStatus.NO_SHOW: {AppointmentStatus.COMPLETED},
    AppointmentStatus.CANCELED: set(),
}


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "client_id"], ["clients.tenant_id", "clients.id"]),
        ForeignKeyConstraint(
            ["tenant_id", "professional_id"], ["professionals.tenant_id", "professionals.id"]
        ),
        ForeignKeyConstraint(["tenant_id", "service_id"], ["services.tenant_id", "services.id"]),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    professional_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(String(200))
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))

    client: Mapped[Client] = relationship(
        lazy="joined", foreign_keys=[client_id], primaryjoin="Appointment.client_id == Client.id"
    )
    professional: Mapped[Professional] = relationship(
        lazy="joined",
        foreign_keys=[professional_id],
        primaryjoin="Appointment.professional_id == Professional.id",
    )
    service: Mapped[Service] = relationship(
        lazy="joined", foreign_keys=[service_id], primaryjoin="Appointment.service_id == Service.id"
    )
