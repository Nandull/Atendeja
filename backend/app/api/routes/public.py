"""Página pública de agendamento: /api/v1/public/{slug}/...

Sem login. Como o RLS bloqueia tudo sem contexto, o fluxo é:
1. define app.public_slug e lê o estabelecimento (política tenants_public_lookup,
   que só libera se o agendamento online estiver ligado);
2. troca para app.tenant_id desse estabelecimento e segue com o RLS normal.

Assim um link nunca enxerga dados de outro estabelecimento, mesmo com bug
no código, e a página só expõe campos escolhidos a dedo (schemas/public.py).
"""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ratelimit import enforce
from app.db.session import SessionLocal, set_rls_context
from app.models import (
    Appointment,
    AppointmentStatus,
    Client,
    Professional,
    ProfessionalService,
    Service,
    Tenant,
)
from app.models.appointment import OPEN
from app.schemas.public import (
    PublicAvailability,
    PublicBookingIn,
    PublicBookingOut,
    PublicBusiness,
    PublicDay,
    PublicProfessional,
    PublicService,
    PublicSlot,
)
from app.services.scheduling import (
    SchedulingError,
    find_block,
    find_conflict,
    free_slots,
    service_terms,
    within_working_hours,
)
from app.services.text import normalize_search

router = APIRouter(prefix="/public", tags=["página pública"])

SLOT_STEP_MIN = 15
MAX_DAYS_PER_QUERY = 14
_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Página de agendamento não encontrada.")


@dataclass
class PublicContext:
    db: Session
    tenant: Tenant

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tenant.timezone)

    def earliest(self, now: datetime) -> datetime:
        """Primeiro horário que o cliente pode marcar (respeita a antecedência)."""
        return now + timedelta(minutes=self.tenant.booking_min_notice_min)

    def last_day(self, now: datetime) -> date:
        return now.astimezone(self.tz).date() + timedelta(days=self.tenant.booking_window_days)


def get_public_context(
    request: Request,
    slug: str = Path(max_length=60, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$"),
) -> Iterator[PublicContext]:
    settings = get_settings()
    enforce(request, "public-read", settings.public_read_per_min, 60)
    db = SessionLocal()
    try:
        set_rls_context(db, public_slug=slug)
        tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
        if tenant is None:
            raise _NOT_FOUND
        # Daqui em diante, só o tenant deste link (RLS normal).
        set_rls_context(db, tenant_id=tenant.id)
        yield PublicContext(db=db, tenant=tenant)
    finally:
        db.close()


def _bookable_links(ctx: PublicContext, service_id: uuid.UUID | None = None):
    """(serviço, profissional, preço) que podem ser agendados pelo link."""
    query = (
        select(ProfessionalService, Professional)
        .join(Professional, Professional.id == ProfessionalService.professional_id)
        .join(Service, Service.id == ProfessionalService.service_id)
        .where(
            Professional.tenant_id == ctx.tenant.id,
            Professional.active.is_(True),
            Service.active.is_(True),
            Service.online_booking.is_(True),
        )
        .order_by(Service.name, Professional.name)
    )
    if service_id:
        query = query.where(Service.id == service_id)
    for link, pro in ctx.db.execute(query):
        price = (
            link.price_cents_override
            if link.price_cents_override is not None
            else link.service.price_cents
        )
        yield link.service, pro, price


@router.get("/{slug}", response_model=PublicBusiness)
def business(ctx: PublicContext = Depends(get_public_context)) -> PublicBusiness:
    services: dict[uuid.UUID, PublicService] = {}
    for service, pro, price in _bookable_links(ctx):
        item = services.get(service.id)
        if item is None:
            item = services[service.id] = PublicService(
                id=service.id,
                name=service.name,
                description=service.description,
                duration_min=service.duration_min,
                price_cents=price,
                price_varies=False,
                professionals=[],
            )
        item.professionals.append(
            PublicProfessional(
                id=pro.id,
                name=pro.name,
                specialty=pro.specialty,
                color=pro.color,
                price_cents=price,
            )
        )
        if price != item.price_cents:
            item.price_varies = True
            item.price_cents = min(item.price_cents, price)
    t = ctx.tenant
    return PublicBusiness(
        name=t.name,
        slug=t.slug,
        niche=t.niche,
        phone=t.phone,
        address=t.address,
        timezone=t.timezone,
        note=t.booking_note,
        min_notice_min=t.booking_min_notice_min,
        window_days=t.booking_window_days,
        services=list(services.values()),
    )


def _candidates(
    ctx: PublicContext, service_id: uuid.UUID, professional_id: uuid.UUID | None
) -> list[Professional]:
    pros = [
        pro
        for _, pro, _ in _bookable_links(ctx, service_id)
        if professional_id is None or pro.id == professional_id
    ]
    if not pros:
        raise HTTPException(422, "Este serviço não está disponível para agendamento online.")
    return pros


@router.get("/{slug}/availability", response_model=PublicAvailability)
def availability(
    service_id: uuid.UUID,
    professional_id: uuid.UUID | None = None,
    start: date | None = Query(default=None, description="Primeiro dia (padrão: hoje)"),
    days: int = Query(default=7, ge=1, le=MAX_DAYS_PER_QUERY),
    ctx: PublicContext = Depends(get_public_context),
) -> PublicAvailability:
    now = datetime.now(UTC)
    today = now.astimezone(ctx.tz).date()
    first = max(start or today, today)
    last = min(first + timedelta(days=days - 1), ctx.last_day(now))

    # Sem preferência de profissional: junta os horários de todos e, em cada
    # horário, indica o primeiro profissional livre (ordem alfabética).
    by_day: dict[date, dict[datetime, uuid.UUID]] = {}
    for pro in _candidates(ctx, service_id, professional_id):
        terms = service_terms(ctx.db, pro, service_id)
        slots = free_slots(
            ctx.db,
            tenant_id=ctx.tenant.id,
            professional=pro,
            terms=terms,
            first_day=first,
            last_day=last,
            tz=ctx.tz,
            earliest=ctx.earliest(now),
            step_min=SLOT_STEP_MIN,
        )
        for day, starts in slots.items():
            bucket = by_day.setdefault(day, {})
            for s in starts:
                bucket.setdefault(s, pro.id)

    result: list[PublicDay] = []
    day = first
    while day <= last:
        bucket = by_day.get(day, {})
        result.append(
            PublicDay(
                date=day,
                slots=[
                    PublicSlot(starts_at=s.astimezone(ctx.tz), professional_id=pid)
                    for s, pid in sorted(bucket.items())
                ],
            )
        )
        day += timedelta(days=1)
    return PublicAvailability(service_id=service_id, professional_id=professional_id, days=result)


def _slot_problem(ctx: PublicContext, pro: Professional, terms, starts_at: datetime) -> str | None:
    """Motivo pelo qual o horário não serve para este profissional (ou None)."""
    ends_at = starts_at + terms.duration
    blocked_until = ends_at + terms.buffer
    if not within_working_hours(ctx.db, pro.id, starts_at, ends_at, ctx.tz):
        return "Horário fora do expediente."
    if find_block(ctx.db, ctx.tenant.id, pro.id, starts_at, blocked_until):
        return "Horário indisponível."
    if find_conflict(ctx.db, pro.id, starts_at, blocked_until):
        return "Este horário acabou de ser ocupado. Escolha outro."
    return None


def _find_or_create_client(ctx: PublicContext, payload: PublicBookingIn) -> Client:
    client = ctx.db.scalar(
        select(Client).where(Client.tenant_id == ctx.tenant.id, Client.phone == payload.phone)
    )
    if client is None:
        client = Client(
            tenant_id=ctx.tenant.id,
            name=payload.name,
            search_name=normalize_search(payload.name),
            phone=payload.phone,
            email=payload.email,
            source="online",
            marketing_consent=payload.marketing_consent,
        )
        try:
            with ctx.db.begin_nested():
                ctx.db.add(client)
                ctx.db.flush()
        except IntegrityError:
            # Mesmo telefone cadastrado ao mesmo tempo por outra requisição.
            client = ctx.db.scalar(
                select(Client).where(
                    Client.tenant_id == ctx.tenant.id, Client.phone == payload.phone
                )
            )
            if client is None:
                raise
        return client
    # Cliente já existe: NÃO trocamos o nome (quem digita pode ser outra pessoa);
    # só completamos o e-mail se estiver vazio.
    if client.email is None and payload.email:
        client.email = payload.email
    if payload.marketing_consent:
        client.marketing_consent = True
    return client


@router.post("/{slug}/appointments", response_model=PublicBookingOut, status_code=201)
def book(
    payload: PublicBookingIn,
    request: Request,
    ctx: PublicContext = Depends(get_public_context),
) -> PublicBookingOut:
    settings = get_settings()
    enforce(request, "public-book", settings.public_booking_per_hour, 3600)
    if payload.website:
        raise HTTPException(422, "Não foi possível concluir o agendamento.")

    now = datetime.now(UTC)
    starts_at = payload.starts_at.astimezone(UTC)
    local = starts_at.astimezone(ctx.tz)
    if local.second or local.microsecond or local.minute % SLOT_STEP_MIN:
        raise HTTPException(422, "Escolha um dos horários da lista.")
    if starts_at < ctx.earliest(now):
        raise HTTPException(422, "Este horário não está mais disponível. Escolha outro.")
    if local.date() > ctx.last_day(now):
        raise HTTPException(422, "Data além do período liberado para agendamento online.")

    open_count = ctx.db.scalar(
        select(func.count())
        .select_from(Appointment)
        .join(Client, Client.id == Appointment.client_id)
        .where(
            Client.phone == payload.phone,
            Appointment.starts_at > now,
            Appointment.status.in_([s.value for s in OPEN]),
        )
    )
    if open_count >= settings.public_max_open_per_phone:
        raise HTTPException(
            422,
            "Você já tem agendamentos marcados. Para marcar mais, fale com o estabelecimento.",
        )

    chosen, terms, problem = None, None, None
    for pro in _candidates(ctx, payload.service_id, payload.professional_id):
        try:
            pro_terms = service_terms(ctx.db, pro, payload.service_id)
        except SchedulingError:
            continue
        problem = _slot_problem(ctx, pro, pro_terms, starts_at)
        if problem is None:
            chosen, terms = pro, pro_terms
            break
    if chosen is None or terms is None:
        raise HTTPException(status.HTTP_409_CONFLICT, problem or "Horário indisponível.")

    client = _find_or_create_client(ctx, payload)
    if not client.active:
        raise HTTPException(422, "Não foi possível agendar pelo link. Fale com o estabelecimento.")

    ends_at = starts_at + terms.duration
    appt = Appointment(
        tenant_id=ctx.tenant.id,
        client_id=client.id,
        professional_id=chosen.id,
        service_id=terms.service.id,
        starts_at=starts_at,
        ends_at=ends_at,
        blocked_until=ends_at + terms.buffer,
        status=AppointmentStatus.SCHEDULED.value,
        price_cents=terms.price_cents,
        origin="online",
        notes=payload.notes.strip() if payload.notes and payload.notes.strip() else None,
    )
    ctx.db.add(appt)
    try:
        ctx.db.commit()
    except IntegrityError as exc:
        ctx.db.rollback()
        # Dois clientes no mesmo horário ao mesmo tempo: o banco barra o segundo.
        if "ex_appointments_no_overlap" in str(exc.orig):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Este horário acabou de ser ocupado. Escolha outro."
            ) from None
        raise

    t = ctx.tenant
    return PublicBookingOut(
        id=appt.id,
        starts_at=starts_at.astimezone(ctx.tz),
        ends_at=ends_at.astimezone(ctx.tz),
        service=terms.service.name,
        professional=chosen.name,
        price_cents=terms.price_cents,
        business_name=t.name,
        business_phone=t.phone,
        business_address=t.address,
        timezone=t.timezone,
    )
