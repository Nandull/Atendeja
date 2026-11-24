import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AwareDatetime
from sqlalchemy import or_, select

from app.api.deps import CurrentContext, get_current_context
from app.api.utils import get_or_404
from app.models import Professional, Role, TimeBlock
from app.models.membership import MANAGER_ROLES
from app.schemas.catalog import TimeBlockCreate, TimeBlockOut

router = APIRouter(prefix="/time-blocks", tags=["bloqueios"])

# Recepção também bloqueia agenda (ex.: profissional avisou que vai faltar).
_SCHEDULERS = MANAGER_ROLES | {Role.RECEPTIONIST}


def _check_can_manage(ctx: CurrentContext, professional_id: uuid.UUID | None) -> None:
    """Gestão e recepção bloqueiam qualquer agenda; o profissional, só a dele."""
    if ctx.role in _SCHEDULERS:
        return
    if professional_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só a gestão pode bloquear o estabelecimento inteiro."
        )
    own = ctx.db.scalar(
        select(Professional.id).where(
            Professional.tenant_id == ctx.tenant.id, Professional.user_id == ctx.user.id
        )
    )
    if own != professional_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Você só pode bloquear a sua agenda.")


@router.get("", response_model=list[TimeBlockOut])
def list_time_blocks(
    start: AwareDatetime = Query(description="Início do período (com fuso)"),
    end: AwareDatetime = Query(description="Fim do período (com fuso)"),
    professional_id: uuid.UUID | None = None,
    ctx: CurrentContext = Depends(get_current_context),
) -> list[TimeBlock]:
    """Bloqueios que encostam no período. Com professional_id, inclui também
    os bloqueios do estabelecimento inteiro, que valem para todos."""
    if start >= end:
        raise HTTPException(422, "start deve ser antes de end.")
    if (end - start).days > 366:
        raise HTTPException(422, "Período máximo de consulta: 1 ano.")
    query = (
        select(TimeBlock)
        .where(
            TimeBlock.tenant_id == ctx.tenant.id,
            TimeBlock.starts_at < end,
            TimeBlock.ends_at > start,
        )
        .order_by(TimeBlock.starts_at)
    )
    if professional_id:
        query = query.where(
            or_(TimeBlock.professional_id == professional_id, TimeBlock.professional_id.is_(None))
        )
    return list(ctx.db.scalars(query))


@router.post("", response_model=TimeBlockOut, status_code=status.HTTP_201_CREATED)
def create_time_block(
    payload: TimeBlockCreate, ctx: CurrentContext = Depends(get_current_context)
) -> TimeBlock:
    _check_can_manage(ctx, payload.professional_id)
    if payload.professional_id:
        get_or_404(ctx, Professional, payload.professional_id, "Profissional")
    block = TimeBlock(tenant_id=ctx.tenant.id, created_by=ctx.user.id, **payload.model_dump())
    ctx.db.add(block)
    ctx.db.commit()
    return block


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_block(
    block_id: uuid.UUID, ctx: CurrentContext = Depends(get_current_context)
) -> Response:
    block = get_or_404(ctx, TimeBlock, block_id, "Bloqueio")
    _check_can_manage(ctx, block.professional_id)
    ctx.db.delete(block)
    ctx.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
