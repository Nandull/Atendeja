import uuid
from itertools import groupby

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentContext, get_current_context, require_roles
from app.api.utils import get_or_404
from app.models import Membership, Professional, ProfessionalService, Service, WorkingHour
from app.models.membership import MANAGER_ROLES
from app.schemas.catalog import (
    ProfessionalCreate,
    ProfessionalOut,
    ProfessionalServiceIn,
    ProfessionalServiceOut,
    ProfessionalUpdate,
    WorkingHourIn,
    WorkingHourOut,
)

router = APIRouter(prefix="/professionals", tags=["profissionais"])


def _out(p: Professional) -> ProfessionalOut:
    services = sorted(p.services, key=lambda ps: ps.service.name.lower())
    return ProfessionalOut(
        id=p.id,
        name=p.name,
        specialty=p.specialty,
        color=p.color,
        user_id=p.user_id,
        active=p.active,
        services=[
            ProfessionalServiceOut(
                service_id=ps.service_id,
                name=ps.service.name,
                duration_min=ps.service.duration_min,
                price_cents=(
                    ps.price_cents_override
                    if ps.price_cents_override is not None
                    else ps.service.price_cents
                ),
                price_cents_override=ps.price_cents_override,
            )
            for ps in services
        ],
        working_hours=[WorkingHourOut.model_validate(wh) for wh in p.working_hours],
    )


def _check_user_is_member(ctx: CurrentContext, user_id: uuid.UUID | None) -> None:
    if user_id is None:
        return
    exists = ctx.db.scalar(
        select(Membership.id).where(
            Membership.tenant_id == ctx.tenant.id, Membership.user_id == user_id
        )
    )
    if not exists:
        raise HTTPException(422, "Este usuário não faz parte da equipe do estabelecimento.")


def _check_services_exist(ctx: CurrentContext, service_ids: set[uuid.UUID]) -> None:
    if not service_ids:
        return
    found = ctx.db.scalar(
        select(func.count())
        .select_from(Service)
        .where(Service.tenant_id == ctx.tenant.id, Service.id.in_(service_ids))
    )
    if found != len(service_ids):
        raise HTTPException(422, "Um ou mais serviços não existem neste estabelecimento.")


def _commit(ctx: CurrentContext) -> None:
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este usuário já está ligado a outro profissional."
        ) from None


@router.get("", response_model=list[ProfessionalOut])
def list_professionals(
    include_inactive: bool = False, ctx: CurrentContext = Depends(get_current_context)
) -> list[ProfessionalOut]:
    query = (
        select(Professional)
        .where(Professional.tenant_id == ctx.tenant.id)
        .order_by(Professional.name)
    )
    if not include_inactive:
        query = query.where(Professional.active.is_(True))
    return [_out(p) for p in ctx.db.scalars(query)]


@router.post("", response_model=ProfessionalOut, status_code=status.HTTP_201_CREATED)
def create_professional(
    payload: ProfessionalCreate, ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES))
) -> ProfessionalOut:
    _check_user_is_member(ctx, payload.user_id)
    service_ids = set(payload.service_ids)
    _check_services_exist(ctx, service_ids)

    p = Professional(
        tenant_id=ctx.tenant.id,
        name=payload.name.strip(),
        specialty=payload.specialty,
        color=payload.color,
        user_id=payload.user_id,
    )
    p.services = [
        ProfessionalService(tenant_id=ctx.tenant.id, service_id=sid) for sid in service_ids
    ]
    ctx.db.add(p)
    _commit(ctx)
    ctx.db.refresh(p)
    return _out(p)


@router.get("/{professional_id}", response_model=ProfessionalOut)
def get_professional(
    professional_id: uuid.UUID, ctx: CurrentContext = Depends(get_current_context)
) -> ProfessionalOut:
    return _out(get_or_404(ctx, Professional, professional_id, "Profissional"))


@router.patch("/{professional_id}", response_model=ProfessionalOut)
def update_professional(
    professional_id: uuid.UUID,
    payload: ProfessionalUpdate,
    ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES)),
) -> ProfessionalOut:
    p = get_or_404(ctx, Professional, professional_id, "Profissional")
    changes = payload.model_dump(exclude_unset=True)
    if "user_id" in changes:
        _check_user_is_member(ctx, changes["user_id"])
    for field, value in changes.items():
        if value is None and field not in ("specialty", "user_id"):
            continue
        setattr(p, field, value.strip() if field == "name" else value)
    _commit(ctx)
    return _out(p)


@router.put("/{professional_id}/services", response_model=ProfessionalOut)
def set_professional_services(
    professional_id: uuid.UUID,
    payload: list[ProfessionalServiceIn],
    ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES)),
) -> ProfessionalOut:
    """Substitui a lista inteira de serviços que o profissional realiza."""
    p = get_or_404(ctx, Professional, professional_id, "Profissional")
    by_id = {item.service_id: item for item in payload}
    _check_services_exist(ctx, set(by_id))
    p.services.clear()
    ctx.db.flush()
    p.services.extend(
        ProfessionalService(
            tenant_id=ctx.tenant.id,
            service_id=item.service_id,
            price_cents_override=item.price_cents_override,
        )
        for item in by_id.values()
    )
    ctx.db.commit()
    ctx.db.refresh(p)
    return _out(p)


@router.put("/{professional_id}/working-hours", response_model=list[WorkingHourOut])
def set_working_hours(
    professional_id: uuid.UUID,
    payload: list[WorkingHourIn],
    ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES)),
) -> list[WorkingHour]:
    """Substitui o expediente semanal inteiro. Permite várias faixas por dia
    (ex.: 08:00-12:00 e 13:00-18:00), desde que não se sobreponham."""
    p = get_or_404(ctx, Professional, professional_id, "Profissional")

    ordered = sorted(payload, key=lambda wh: (wh.weekday, wh.start_time))
    for _, day in groupby(ordered, key=lambda wh: wh.weekday):
        ranges = list(day)
        for previous, current in zip(ranges, ranges[1:], strict=False):
            if current.start_time < previous.end_time:
                raise HTTPException(422, "Há faixas de horário sobrepostas no mesmo dia.")

    p.working_hours.clear()
    ctx.db.flush()
    p.working_hours.extend(
        WorkingHour(tenant_id=ctx.tenant.id, **wh.model_dump()) for wh in ordered
    )
    ctx.db.commit()
    ctx.db.refresh(p)
    return p.working_hours
