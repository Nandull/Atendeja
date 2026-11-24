"""Regras de agenda: expediente, bloqueios, horários livres.

A trava definitiva contra dois atendimentos no mesmo horário é a constraint
EXCLUDE do banco. Estas funções servem para dar mensagens claras ANTES de
chegar nela e para calcular os horários livres.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Appointment,
    Professional,
    ProfessionalService,
    Service,
    TimeBlock,
    WorkingHour,
)
from app.models.appointment import OCCUPYING


@dataclass
class ServiceTerms:
    """O que vale para este profissional neste serviço."""

    service: Service
    duration: timedelta
    buffer: timedelta
    price_cents: int


class SchedulingError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def service_terms(db: Session, professional: Professional, service_id: uuid.UUID) -> ServiceTerms:
    link = db.scalar(
        select(ProfessionalService).where(
            ProfessionalService.professional_id == professional.id,
            ProfessionalService.service_id == service_id,
        )
    )
    if link is None:
        raise SchedulingError("Este profissional não realiza este serviço.")
    service = link.service
    if not service.active:
        raise SchedulingError("Este serviço está desativado.")
    price = (
        link.price_cents_override if link.price_cents_override is not None else service.price_cents
    )
    return ServiceTerms(
        service=service,
        duration=timedelta(minutes=service.duration_min),
        buffer=timedelta(minutes=service.buffer_min),
        price_cents=price,
    )


def _ranges_for(db: Session, professional_id: uuid.UUID, weekday: int) -> list[WorkingHour]:
    return list(
        db.scalars(
            select(WorkingHour)
            .where(WorkingHour.professional_id == professional_id, WorkingHour.weekday == weekday)
            .order_by(WorkingHour.start_time)
        )
    )


def within_working_hours(
    db: Session, professional_id: uuid.UUID, starts: datetime, ends: datetime, tz: ZoneInfo
) -> bool:
    local_start, local_end = starts.astimezone(tz), ends.astimezone(tz)
    if local_start.date() != local_end.date():
        return False
    return any(
        wh.start_time <= local_start.time() and local_end.time() <= wh.end_time
        for wh in _ranges_for(db, professional_id, local_start.weekday())
    )


def find_block(
    db: Session, tenant_id: uuid.UUID, professional_id: uuid.UUID, starts: datetime, ends: datetime
) -> TimeBlock | None:
    return db.scalar(
        select(TimeBlock).where(
            TimeBlock.tenant_id == tenant_id,
            or_(TimeBlock.professional_id == professional_id, TimeBlock.professional_id.is_(None)),
            TimeBlock.starts_at < ends,
            TimeBlock.ends_at > starts,
        )
    )


def find_conflict(
    db: Session,
    professional_id: uuid.UUID,
    starts: datetime,
    blocked_until: datetime,
    ignore_id: uuid.UUID | None = None,
) -> Appointment | None:
    query = select(Appointment).where(
        Appointment.professional_id == professional_id,
        Appointment.status.in_([s.value for s in OCCUPYING]),
        Appointment.starts_at < blocked_until,
        Appointment.blocked_until > starts,
    )
    if ignore_id:
        query = query.where(Appointment.id != ignore_id)
    return db.scalar(query.limit(1))


def free_slots(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    professional: Professional,
    terms: ServiceTerms,
    first_day: date,
    last_day: date,
    tz: ZoneInfo,
    earliest: datetime,
    step_min: int = 15,
) -> dict[date, list[datetime]]:
    """Horários de início livres em um intervalo de dias (no fuso do estabelecimento).

    Um horário é livre se o atendimento cabe inteiro no expediente, começa a
    partir de `earliest` e o período ocupado (duração + intervalo) não encosta
    em bloqueio nem em outro atendimento.

    Faz só 3 consultas para o intervalo inteiro (expediente, agendamentos e
    bloqueios), então montar a semana da página pública continua rápido.
    """
    hours: dict[int, list[WorkingHour]] = {}
    for wh in db.scalars(
        select(WorkingHour)
        .where(WorkingHour.professional_id == professional.id)
        .order_by(WorkingHour.start_time)
    ):
        hours.setdefault(wh.weekday, []).append(wh)
    if not hours or last_day < first_day:
        return {}

    range_start = datetime.combine(first_day, time.min, tzinfo=tz)
    range_end = datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=tz)
    busy: list[tuple[datetime, datetime]] = [
        (a.starts_at, a.blocked_until)
        for a in db.scalars(
            select(Appointment).where(
                Appointment.professional_id == professional.id,
                Appointment.status.in_([s.value for s in OCCUPYING]),
                Appointment.starts_at < range_end,
                Appointment.blocked_until > range_start,
            )
        )
    ]
    busy += [
        (b.starts_at, b.ends_at)
        for b in db.scalars(
            select(TimeBlock).where(
                TimeBlock.tenant_id == tenant_id,
                or_(
                    TimeBlock.professional_id == professional.id,
                    TimeBlock.professional_id.is_(None),
                ),
                TimeBlock.starts_at < range_end,
                TimeBlock.ends_at > range_start,
            )
        )
    ]

    step = timedelta(minutes=step_min)
    result: dict[date, list[datetime]] = {}
    day = first_day
    while day <= last_day:
        slots: list[datetime] = []
        for wh in hours.get(day.weekday(), []):
            t = datetime.combine(day, wh.start_time, tzinfo=tz)
            range_close = datetime.combine(day, wh.end_time, tzinfo=tz)
            while t + terms.duration <= range_close:
                occupied_until = t + terms.duration + terms.buffer
                if t >= earliest and not any(s < occupied_until and e > t for s, e in busy):
                    slots.append(t)
                t += step
        result[day] = slots
        day += timedelta(days=1)
    return result


def available_slots(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    professional: Professional,
    terms: ServiceTerms,
    day: date,
    tz: ZoneInfo,
    now: datetime,
    step_min: int = 15,
) -> list[datetime]:
    """Horários livres de um único dia (usado pela agenda interna)."""
    return free_slots(
        db,
        tenant_id=tenant_id,
        professional=professional,
        terms=terms,
        first_day=day,
        last_day=day,
        tz=tz,
        earliest=now,
        step_min=step_min,
    ).get(day, [])
