import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentContext, get_current_context, require_roles
from app.api.utils import get_or_404
from app.models import Service
from app.models.membership import MANAGER_ROLES
from app.schemas.catalog import ServiceCreate, ServiceOut, ServiceUpdate

router = APIRouter(prefix="/services", tags=["serviços"])

_DUPLICATE = HTTPException(status.HTTP_409_CONFLICT, "Já existe um serviço com este nome.")


@router.get("", response_model=list[ServiceOut])
def list_services(
    include_inactive: bool = False, ctx: CurrentContext = Depends(get_current_context)
) -> list[Service]:
    query = select(Service).where(Service.tenant_id == ctx.tenant.id).order_by(Service.name)
    if not include_inactive:
        query = query.where(Service.active.is_(True))
    return list(ctx.db.scalars(query))


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate, ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES))
) -> Service:
    service = Service(tenant_id=ctx.tenant.id, **payload.model_dump())
    service.name = service.name.strip()
    ctx.db.add(service)
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise _DUPLICATE from None
    return service


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(
    service_id: uuid.UUID, ctx: CurrentContext = Depends(get_current_context)
) -> Service:
    return get_or_404(ctx, Service, service_id, "Serviço")


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES)),
) -> Service:
    service = get_or_404(ctx, Service, service_id, "Serviço")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None and field != "description":
            continue  # campos obrigatórios não podem ser apagados
        setattr(service, field, value.strip() if field == "name" else value)
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise _DUPLICATE from None
    return service
