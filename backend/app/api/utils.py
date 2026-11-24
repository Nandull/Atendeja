import uuid

from fastapi import HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentContext


def get_or_404[T](ctx: CurrentContext, model: type[T], obj_id: uuid.UUID, label: str) -> T:
    """Busca um registro do estabelecimento atual ou devolve 404.

    O filtro por tenant_id aqui é redundante com o RLS de propósito:
    duas camadas de proteção.
    """
    obj = ctx.db.scalar(
        select(model).where(model.id == obj_id, model.tenant_id == ctx.tenant.id)  # type: ignore[attr-defined]
    )
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} não encontrado.")
    return obj


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
