import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentContext, get_current_context, require_roles
from app.core.security import hash_password
from app.models import Membership, Role, User
from app.models.membership import MANAGER_ROLES
from app.schemas.member import MemberCreate, MemberOut, MemberRoleUpdate

router = APIRouter(prefix="/members", tags=["equipe"])


def _out(m: Membership) -> MemberOut:
    return MemberOut(id=m.id, user_id=m.user_id, name=m.user.name, email=m.user.email, role=m.role)


def _get_membership(ctx: CurrentContext, member_id: uuid.UUID) -> Membership:
    # Mesmo filtrando por tenant aqui, o RLS impediria ver vínculo de outro estabelecimento.
    m = ctx.db.scalar(
        select(Membership).where(Membership.id == member_id, Membership.tenant_id == ctx.tenant.id)
    )
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membro não encontrado.")
    return m


def _owner_count(ctx: CurrentContext) -> int:
    return ctx.db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.tenant_id == ctx.tenant.id, Membership.role == Role.OWNER.value)
    )


@router.get("", response_model=list[MemberOut])
def list_members(ctx: CurrentContext = Depends(get_current_context)) -> list[MemberOut]:
    rows = ctx.db.scalars(
        select(Membership)
        .where(Membership.tenant_id == ctx.tenant.id)
        .order_by(Membership.created_at)
    )
    return [_out(m) for m in rows]


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    payload: MemberCreate, ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES))
) -> MemberOut:
    if payload.role == Role.OWNER and ctx.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o dono pode adicionar outro dono.")

    user = ctx.db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        if not payload.password:
            raise HTTPException(
                422,
                "Informe uma senha inicial para o novo usuário.",
            )
        user = User(
            email=payload.email,
            name=payload.name.strip(),
            password_hash=hash_password(payload.password),
        )
        ctx.db.add(user)
        ctx.db.flush()

    membership = Membership(tenant_id=ctx.tenant.id, user_id=user.id, role=payload.role.value)
    ctx.db.add(membership)
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Esta pessoa já faz parte da equipe."
        ) from None
    ctx.db.refresh(membership)
    return _out(membership)


@router.patch("/{member_id}", response_model=MemberOut)
def change_role(
    member_id: uuid.UUID,
    payload: MemberRoleUpdate,
    ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES)),
) -> MemberOut:
    m = _get_membership(ctx, member_id)
    touches_owner = m.role == Role.OWNER.value or payload.role == Role.OWNER
    if touches_owner and ctx.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o dono pode alterar o perfil de dono.")
    if m.role == Role.OWNER.value and payload.role != Role.OWNER and _owner_count(ctx) <= 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "O estabelecimento precisa ter ao menos um dono."
        )
    m.role = payload.role.value
    ctx.db.commit()
    return _out(m)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    member_id: uuid.UUID, ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES))
) -> Response:
    m = _get_membership(ctx, member_id)
    if m.role == Role.OWNER.value:
        if ctx.role != Role.OWNER:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o dono pode remover um dono.")
        if _owner_count(ctx) <= 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "O estabelecimento precisa ter ao menos um dono."
            )
    ctx.db.delete(m)
    ctx.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
