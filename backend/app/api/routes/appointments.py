import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentContext, get_current_context
from app.api.utils import get_or_404
from app.models import Appointment, AppointmentStatus, Client, Professional, Role
from app.models.appointment import OPEN, TRANSITIONS
from app.models.membership import MANAGER_ROLES
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentUpdate,
    ClientRef,
    ProfessionalRef,
    Ref,
    SlotsOut,
    StatusChange,
)
from app.services.scheduling import (
    SchedulingError,
    available_slots,
    find_block,
    find_conflict,
    service_terms,
    within_working_hours,
)

router = APIRouter(tags=["agenda"])

_SCHEDULERS = MANAGER_ROLES | {Role.RECEPTIONIST}


def to_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=a.id,
        client=ClientRef(id=a.client.id, name=a.client.name, phone=a.client.phone),
        professional=ProfessionalRef(
            id=a.professional.id, name=a.professional.name, color=a.professional.color
        ),
        service=Ref(id=a.service.id, name=a.service.name),
        starts_at=a.starts_at,
        ends_at=a.ends_at,
        blocked_until=a.blocked_until,
        status=AppointmentStatus(a.status),
        price_cents=a.price_cents,
        origin=a.origin,
        notes=a.notes,
        cancel_reason=a.cancel_reason,
        created_at=a.created_at,
    )


def _own_professional_id(ctx: CurrentContext) -> uuid.UUID | None:
    return ctx.db.scalar(
        select(Professional.id).where(
            Professional.tenant_id == ctx.tenant.id, Professional.user_id == ctx.user.id
        )
    )


def _check_agenda_access(ctx: CurrentContext, professional_id: uuid.UUID) -> None:
    """Gestão e recepção mexem em qualquer agenda; o profissional, só na dele."""
    if ctx.role in _SCHEDULERS:
        return
    if _own_professional_id(ctx) != professional_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você só pode mexer na sua agenda.")


def _validate_slot(
    ctx: CurrentContext,
    professional: Professional,
    service_id: uuid.UUID,
    starts_at: datetime,
    allow_outside_hours: bool,
    ignore_id: uuid.UUID | None = None,
):
    """Valida e devolve (terms, ends_at, blocked_until). Mensagens claras para a tela."""
    if not professional.active:
        raise HTTPException(422, "Este profissional está desativado.")
    try:
        terms = service_terms(ctx.db, professional, service_id)
    except SchedulingError as exc:
        raise HTTPException(exc.status_code, exc.message) from None

    ends_at = starts_at + terms.duration
    blocked_until = ends_at + terms.buffer
    tz = ZoneInfo(ctx.tenant.timezone)

    if allow_outside_hours and ctx.role not in _SCHEDULERS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só gestão e recepção fazem encaixes.")
    if not allow_outside_hours and not within_working_hours(
        ctx.db, professional.id, starts_at, ends_at, tz
    ):
        raise HTTPException(422, "Fora do expediente do profissional.")
    block = find_block(ctx.db, ctx.tenant.id, professional.id, starts_at, blocked_until)
    if block:
        reason = f" ({block.reason})" if block.reason else ""
        raise HTTPException(status.HTTP_409_CONFLICT, f"Horário bloqueado{reason}.")
    conflict = find_conflict(ctx.db, professional.id, starts_at, blocked_until, ignore_id)
    if conflict:
        hora = conflict.starts_at.astimezone(tz).strftime("%H:%M")
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Horário ocupado: {conflict.client.name} às {hora}.",
        )
    return terms, ends_at, blocked_until


def _commit_or_conflict(ctx: CurrentContext) -> None:
    try:
        ctx.db.commit()
    except IntegrityError as exc:
        ctx.db.rollback()
        # A checagem acima pode perder uma corrida (dois cliques ao mesmo tempo);
        # nesse caso a constraint do banco barra e devolvemos o mesmo 409.
        if "ex_appointments_no_overlap" in str(exc.orig):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Horário acabou de ser ocupado. Escolha outro."
            ) from None
        raise


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    start: AwareDatetime = Query(description="Início do período (com fuso)"),
    end: AwareDatetime = Query(description="Fim do período (com fuso)"),
    professional_id: uuid.UUID | None = None,
    include_canceled: bool = False,
    ctx: CurrentContext = Depends(get_current_context),
) -> list[AppointmentOut]:
    if start >= end:
        raise HTTPException(422, "start deve ser antes de end.")
    if end - start > timedelta(days=62):
        raise HTTPException(422, "Período máximo de consulta: 62 dias.")
    query = (
        select(Appointment)
        .where(
            Appointment.tenant_id == ctx.tenant.id,
            Appointment.starts_at < end,
            Appointment.ends_at > start,
        )
        .order_by(Appointment.starts_at)
    )
    if ctx.role == Role.PROFESSIONAL:
        # Profissional vê só a própria agenda.
        own = _own_professional_id(ctx)
        if own is None:
            return []
        query = query.where(Appointment.professional_id == own)
    elif professional_id:
        query = query.where(Appointment.professional_id == professional_id)
    if not include_canceled:
        query = query.where(Appointment.status != AppointmentStatus.CANCELED.value)
    return [to_out(a) for a in ctx.db.scalars(query)]


@router.post("/appointments", response_model=AppointmentOut, status_code=201)
def create_appointment(
    payload: AppointmentCreate, ctx: CurrentContext = Depends(get_current_context)
) -> AppointmentOut:
    _check_agenda_access(ctx, payload.professional_id)
    professional = get_or_404(ctx, Professional, payload.professional_id, "Profissional")
    client = get_or_404(ctx, Client, payload.client_id, "Cliente")
    if not client.active:
        raise HTTPException(422, "Este cliente está desativado.")
    terms, ends_at, blocked_until = _validate_slot(
        ctx, professional, payload.service_id, payload.starts_at, payload.allow_outside_hours
    )
    appt = Appointment(
        tenant_id=ctx.tenant.id,
        client_id=client.id,
        professional_id=professional.id,
        service_id=terms.service.id,
        starts_at=payload.starts_at,
        ends_at=ends_at,
        blocked_until=blocked_until,
        status=AppointmentStatus.SCHEDULED.value,
        price_cents=terms.price_cents,
        origin="manual",
        notes=payload.notes,
        created_by=ctx.user.id,
    )
    ctx.db.add(appt)
    _commit_or_conflict(ctx)
    ctx.db.refresh(appt)
    return to_out(appt)


@router.get("/appointments/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: uuid.UUID, ctx: CurrentContext = Depends(get_current_context)
) -> AppointmentOut:
    appt = get_or_404(ctx, Appointment, appointment_id, "Agendamento")
    if ctx.role == Role.PROFESSIONAL:
        _check_agenda_access(ctx, appt.professional_id)
    return to_out(appt)


@router.patch("/appointments/{appointment_id}", response_model=AppointmentOut)
def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    ctx: CurrentContext = Depends(get_current_context),
) -> AppointmentOut:
    appt = get_or_404(ctx, Appointment, appointment_id, "Agendamento")
    _check_agenda_access(ctx, appt.professional_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"allow_outside_hours"})

    if "notes" in changes:
        appt.notes = changes.pop("notes")
    moving = {k: v for k, v in changes.items() if v is not None}
    if moving:
        if AppointmentStatus(appt.status) not in OPEN:
            raise HTTPException(422, "Só dá para reagendar atendimentos em aberto.")
        professional_id = moving.get("professional_id", appt.professional_id)
        _check_agenda_access(ctx, professional_id)
        professional = get_or_404(ctx, Professional, professional_id, "Profissional")
        starts_at = moving.get("starts_at", appt.starts_at)
        service_id = moving.get("service_id", appt.service_id)
        terms, ends_at, blocked_until = _validate_slot(
            ctx, professional, service_id, starts_at, payload.allow_outside_hours, appt.id
        )
        appt.professional_id = professional.id
        appt.service_id = terms.service.id
        appt.starts_at, appt.ends_at, appt.blocked_until = starts_at, ends_at, blocked_until
        if "service_id" in moving or "professional_id" in moving:
            appt.price_cents = terms.price_cents
        # Mudou o horário: volta para "agendado" até o cliente confirmar de novo.
        appt.status = AppointmentStatus.SCHEDULED.value
    _commit_or_conflict(ctx)
    ctx.db.refresh(appt)
    return to_out(appt)


@router.post("/appointments/{appointment_id}/status", response_model=AppointmentOut)
def change_status(
    appointment_id: uuid.UUID,
    payload: StatusChange,
    ctx: CurrentContext = Depends(get_current_context),
) -> AppointmentOut:
    appt = get_or_404(ctx, Appointment, appointment_id, "Agendamento")
    _check_agenda_access(ctx, appt.professional_id)
    current, target = AppointmentStatus(appt.status), payload.status
    if target == current:
        return to_out(appt)
    if target not in TRANSITIONS[current]:
        raise HTTPException(422, f"Não é possível mudar de '{current}' para '{target}'.")
    attendance = {AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW}
    if target in attendance and appt.starts_at > datetime.now(UTC):
        raise HTTPException(422, "Atendimento ainda não começou.")
    appt.status = target.value
    appt.status_changed_at = datetime.now(UTC)
    if target == AppointmentStatus.CANCELED:
        appt.cancel_reason = payload.cancel_reason
    # Voltar de falta para concluído ocupa a agenda de novo: o banco revalida.
    _commit_or_conflict(ctx)
    ctx.db.refresh(appt)
    return to_out(appt)


@router.get("/availability", response_model=SlotsOut)
def availability(
    professional_id: uuid.UUID,
    service_id: uuid.UUID,
    day: date = Query(alias="date", description="Dia no fuso do estabelecimento (AAAA-MM-DD)"),
    ctx: CurrentContext = Depends(get_current_context),
) -> SlotsOut:
    professional = get_or_404(ctx, Professional, professional_id, "Profissional")
    try:
        terms = service_terms(ctx.db, professional, service_id)
    except SchedulingError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    slots = available_slots(
        ctx.db,
        tenant_id=ctx.tenant.id,
        professional=professional,
        terms=terms,
        day=day,
        tz=ZoneInfo(ctx.tenant.timezone),
        now=datetime.now(UTC),
    )
    return SlotsOut(
        date=day,
        professional_id=professional.id,
        service_id=service_id,
        duration_min=terms.service.duration_min,
        price_cents=terms.price_cents,
        slots=slots,
    )
