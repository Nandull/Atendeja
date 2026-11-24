"""Sessões de banco com contexto de tenant para o Row-Level Security.

Cada transação executa `set_config('app.tenant_id', ...)` e
`set_config('app.user_id', ...)` com escopo LOCAL (vale só até o COMMIT).
As políticas de RLS no Postgres leem esses valores; sem eles, nenhuma linha
de tabela de tenant é visível. Ou seja: se o código esquecer o filtro,
o banco bloqueia mesmo assim (falha fechada).
"""

import uuid
from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_SET_CONTEXT = text(
    "SELECT set_config('app.tenant_id', :tid, true), "
    "set_config('app.user_id', :uid, true), "
    "set_config('app.public_slug', :slug, true)"
)


def _context_params(session: Session) -> dict[str, str]:
    tenant_id = session.info.get("tenant_id")
    user_id = session.info.get("user_id")
    return {
        "tid": str(tenant_id) if tenant_id else "",
        "uid": str(user_id) if user_id else "",
        "slug": session.info.get("public_slug") or "",
    }


@event.listens_for(Session, "after_begin")
def _apply_rls_context(session: Session, transaction, connection) -> None:
    connection.execute(_SET_CONTEXT, _context_params(session))


def set_rls_context(
    session: Session,
    *,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    public_slug: str | None = None,
) -> None:
    """Define o tenant/usuário da sessão. Vale a partir da próxima transação
    e também é aplicado imediatamente se já houver uma transação aberta.

    `public_slug` só é usado pela página pública, para achar o estabelecimento
    pelo link antes de saber o tenant_id (ver política tenants_public_lookup).
    """
    session.info["tenant_id"] = tenant_id
    session.info["user_id"] = user_id
    session.info["public_slug"] = public_slug
    if session.in_transaction():
        session.execute(_SET_CONTEXT, _context_params(session))


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
