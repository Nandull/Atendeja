import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentContext, get_current_context
from app.api.utils import escape_like, get_or_404
from app.models import Appointment, Client, Role
from app.schemas.appointment import ClientHistory, ClientStats
from app.schemas.catalog import ClientCreate, ClientOut, ClientPage, ClientUpdate
from app.services.text import normalize_search

router = APIRouter(prefix="/clients", tags=["clientes"])


def _duplicate_phone(ctx: CurrentContext, phone: str) -> HTTPException:
    existing = ctx.db.scalar(
        select(Client).where(Client.tenant_id == ctx.tenant.id, Client.phone == phone)
    )
    detail = {"message": "Já existe um cliente com este telefone."}
    if existing:
        detail |= {"client_id": str(existing.id), "name": existing.name}
    return HTTPException(status.HTTP_409_CONFLICT, detail)


@router.get("", response_model=ClientPage)
def list_clients(
    q: str | None = Query(default=None, max_length=120, description="Nome ou telefone"),
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: CurrentContext = Depends(get_current_context),
) -> ClientPage:
    filters = [Client.tenant_id == ctx.tenant.id]
    if not include_inactive:
        filters.append(Client.active.is_(True))
    if q and q.strip():
        digits = re.sub(r"\D", "", q)
        # Se a busca tem letras, é nome; se tem 3+ dígitos e nada mais, é telefone.
        if digits and len(digits) >= 3 and not re.search(r"[^\d\s()+\-.]", q):
            filters.append(Client.phone.like(f"%{escape_like(digits)}%"))
        else:
            term = escape_like(normalize_search(q))
            filters.append(Client.search_name.like(f"%{term}%"))

    total = ctx.db.scalar(select(func.count()).select_from(Client).where(*filters))
    rows = ctx.db.scalars(
        select(Client).where(*filters).order_by(Client.search_name).limit(limit).offset(offset)
    )
    return ClientPage(
        items=[ClientOut.model_validate(c) for c in rows], total=total, limit=limit, offset=offset
    )


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate, ctx: CurrentContext = Depends(get_current_context)
) -> Client:
    data = payload.model_dump()
    data["name"] = data["name"].strip()
    client = Client(tenant_id=ctx.tenant.id, search_name=normalize_search(data["name"]), **data)
    ctx.db.add(client)
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise _duplicate_phone(ctx, payload.phone) from None
    return client


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: uuid.UUID, ctx: CurrentContext = Depends(get_current_context)) -> Client:
    return get_or_404(ctx, Client, client_id, "Cliente")


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    ctx: CurrentContext = Depends(get_current_context),
) -> Client:
    client = get_or_404(ctx, Client, client_id, "Cliente")
    required = {"name", "phone", "marketing_consent", "active"}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None and field in required:
            continue
        if field == "name":
            value = value.strip()
            client.search_name = normalize_search(value)
        setattr(client, field, value)
    try:
        ctx.db.commit()
    except IntegrityError:
        ctx.db.rollback()
        raise _duplicate_phone(ctx, client.phone) from None
    return client


@router.get("/{client_id}/history", response_model=ClientHistory)
def client_history(
    client_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    ctx: CurrentContext = Depends(get_current_context),
) -> ClientHistory:
    """Histórico de atendimentos e indicadores do cliente (frequência, gasto)."""
    from app.api.routes.appointments import to_out  # evita import circular

    client = get_or_404(ctx, Client, client_id, "Cliente")
    stats_row = ctx.db.execute(
        text("SELECT * FROM v_client_stats WHERE client_id = :id"), {"id": client.id}
    ).one()

    avg_gap = None
    if stats_row.completed >= 2:
        span_days = (stats_row.last_visit - stats_row.first_visit).total_seconds() / 86400
        avg_gap = round(span_days / (stats_row.completed - 1), 1)

    query = (
        select(Appointment)
        .where(Appointment.tenant_id == ctx.tenant.id, Appointment.client_id == client.id)
        .order_by(Appointment.starts_at.desc())
        .limit(limit)
    )
    if ctx.role == Role.PROFESSIONAL:
        query = query.where(Appointment.professional.has(user_id=ctx.user.id))
    return ClientHistory(
        stats=ClientStats(
            completed=stats_row.completed,
            no_show=stats_row.no_show,
            canceled=stats_row.canceled,
            upcoming=stats_row.upcoming,
            total_spent_cents=stats_row.total_spent_cents,
            first_visit=stats_row.first_visit,
            last_visit=stats_row.last_visit,
            avg_days_between_visits=avg_gap,
        ),
        appointments=[to_out(a) for a in ctx.db.scalars(query)],
    )
