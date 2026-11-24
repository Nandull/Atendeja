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


@event.listens_for(Session, "after_begin")
def _apply_rls_context(session: Session, transaction, connection) -> None:
    tenant_id = session.info.get("tenant_id")
    user_id = session.info.get("user_id")
    connection.execute(
        text(
            "SELECT set_config('app.tenant_id', :tid, true), set_config('app.user_id', :uid, true)"
        ),
        {"tid": str(tenant_id) if tenant_id else "", "uid": str(user_id) if user_id else ""},
    )


def set_rls_context(
    session: Session, *, tenant_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None
) -> None:
    """Define o tenant/usuário da sessão. Vale a partir da próxima transação
    e também é aplicado imediatamente se já houver uma transação aberta."""
    session.info["tenant_id"] = tenant_id
    session.info["user_id"] = user_id
    if session.in_transaction():
        session.execute(
            text(
                "SELECT set_config('app.tenant_id', :tid, true), "
                "set_config('app.user_id', :uid, true)"
            ),
            {"tid": str(tenant_id) if tenant_id else "", "uid": str(user_id) if user_id else ""},
        )


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
