from collections.abc import Callable, Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import InvalidToken, decode_token
from app.db.session import SessionLocal, set_rls_context
from app.models import Membership, Role, Tenant, User

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sessão inválida ou expirada. Faça login novamente.",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class CurrentContext:
    """Tudo que uma rota autenticada precisa: banco já filtrado pelo tenant,
    usuário, estabelecimento e perfil de acesso."""

    db: Session
    user: User
    tenant: Tenant
    membership: Membership

    @property
    def role(self) -> Role:
        return Role(self.membership.role)


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(ACCESS_COOKIE)


def get_current_context(request: Request) -> Iterator[CurrentContext]:
    token = _extract_token(request)
    if not token:
        raise _UNAUTHORIZED
    try:
        user_id, tenant_id = decode_token(token, "access")
    except InvalidToken:
        raise _UNAUTHORIZED from None

    db = SessionLocal()
    try:
        set_rls_context(db, tenant_id=tenant_id, user_id=user_id)
        # Confere no banco a cada requisição: se o usuário foi removido da
        # equipe ou desativado, o acesso cai na hora, sem esperar o token vencer.
        membership = db.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant_id, Membership.user_id == user_id
            )
        )
        if membership is None or not membership.user.is_active:
            raise _UNAUTHORIZED
        if membership.tenant.status != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Estabelecimento suspenso.")
        yield CurrentContext(
            db=db, user=membership.user, tenant=membership.tenant, membership=membership
        )
    finally:
        db.close()


def require_roles(*roles: Role) -> Callable[..., CurrentContext]:
    allowed = set(roles)

    def dependency(ctx: CurrentContext = Depends(get_current_context)) -> CurrentContext:
        if ctx.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Seu perfil não tem permissão para esta ação."
            )
        return ctx

    return dependency
