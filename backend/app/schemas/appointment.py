import uuid
from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, Field

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    client_id: uuid.UUID
    professional_id: uuid.UUID
    service_id: uuid.UUID
    starts_at: AwareDatetime
    notes: str | None = Field(default=None, max_length=2000)
    allow_outside_hours: bool = Field(
        default=False, description="Encaixe fora do expediente (gestão e recepção)"
    )


class AppointmentUpdate(BaseModel):
    """Reagendar: mudar horário, profissional ou serviço, ou editar observação."""

    starts_at: AwareDatetime | None = None
    professional_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    allow_outside_hours: bool = False


class StatusChange(BaseModel):
    status: AppointmentStatus
    cancel_reason: str | None = Field(default=None, max_length=200)


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class ProfessionalRef(Ref):
    color: str


class ClientRef(Ref):
    phone: str


class AppointmentOut(BaseModel):
    id: uuid.UUID
    client: ClientRef
    professional: ProfessionalRef
    service: Ref
    starts_at: datetime
    ends_at: datetime
    blocked_until: datetime
    status: AppointmentStatus
    price_cents: int
    origin: str
    notes: str | None
    cancel_reason: str | None
    created_at: datetime


class SlotsOut(BaseModel):
    date: date
    professional_id: uuid.UUID
    service_id: uuid.UUID
    duration_min: int
    price_cents: int
    slots: list[datetime]


class ClientStats(BaseModel):
    completed: int
    no_show: int
    canceled: int
    upcoming: int
    total_spent_cents: int = Field(description="Soma dos atendimentos concluídos")
    first_visit: datetime | None
    last_visit: datetime | None
    avg_days_between_visits: float | None


class ClientHistory(BaseModel):
    stats: ClientStats
    appointments: list[AppointmentOut]
