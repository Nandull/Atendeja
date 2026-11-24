from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentContext, get_current_context, require_roles
from app.api.routes.auth import _session_out
from app.models.membership import MANAGER_ROLES
from app.schemas.auth import SessionOut, TenantOut
from app.schemas.tenant import TenantUpdate

router = APIRouter(tags=["conta"])


@router.get("/me", response_model=SessionOut)
def me(ctx: CurrentContext = Depends(get_current_context)) -> SessionOut:
    return _session_out(ctx.db, ctx.membership)


@router.get("/tenant", response_model=TenantOut)
def get_tenant(ctx: CurrentContext = Depends(get_current_context)) -> TenantOut:
    return TenantOut.model_validate(ctx.tenant)


@router.patch("/tenant", response_model=TenantOut)
def update_tenant(
    payload: TenantUpdate,
    ctx: CurrentContext = Depends(require_roles(*MANAGER_ROLES)),
) -> TenantOut:
    changes = payload.model_dump(exclude_unset=True)
    if "timezone" in changes:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(changes["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(422, "Fuso horário inválido.") from None
    nullable = {"phone", "address", "booking_note"}
    for field, value in changes.items():
        if value is None and field not in nullable:
            continue  # campo obrigatório: null significa "não mexer"
        if isinstance(value, str):
            value = value.strip() or (None if field in nullable else value)
        setattr(ctx.tenant, field, value)
    ctx.db.commit()
    return TenantOut.model_validate(ctx.tenant)
