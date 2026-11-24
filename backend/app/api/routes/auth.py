import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ACCESS_COOKIE, REFRESH_COOKIE, CurrentContext, get_current_context
from app.core.config import get_settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    InvalidToken,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import SessionLocal, set_rls_context
from app.models import Membership, Role, Tenant, User
from app.schemas.auth import (
    LoginIn,
    SessionOut,
    SignupIn,
    SwitchTenantIn,
    TenantChoice,
    TenantOut,
    UserOut,
)
from app.services.slugs import slug_candidates, slugify

router = APIRouter(prefix="/auth", tags=["auth"])

TRIAL_DAYS = 14
_INVALID_LOGIN = HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")


# --- utilitários ------------------------------------------------------------


def _set_auth_cookies(response: Response, user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    settings = get_settings()
    access = create_token(user_id=user_id, tenant_id=tenant_id, token_type="access")
    refresh = create_token(user_id=user_id, tenant_id=tenant_id, token_type="refresh")
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        ACCESS_COOKIE, access, max_age=settings.access_token_minutes * 60, path="/", **common
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.refresh_token_days * 86400,
        path="/api/v1/auth",
        **common,
    )
    return access


def _clear_auth_cookies(response: Response) -> None:
    domain = get_settings().cookie_domain
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth", domain=domain)


def _user_memberships(db: Session, user_id: uuid.UUID) -> list[Membership]:
    # O RLS permite ao usuário logado ver os próprios vínculos (política memberships_own_user).
    return list(
        db.scalars(
            select(Membership).where(Membership.user_id == user_id).order_by(Membership.created_at)
        )
    )


def _session_out(
    db: Session, membership: Membership, access_token: str | None = None
) -> SessionOut:
    return SessionOut(
        user=UserOut.model_validate(membership.user),
        tenant=TenantOut.model_validate(membership.tenant),
        role=membership.role,
        tenants=[
            TenantChoice(slug=m.tenant.slug, name=m.tenant.name, role=m.role)
            for m in _user_memberships(db, membership.user_id)
        ],
        access_token=access_token,
    )


# --- rotas --------------------------------------------------------------------


@router.post("/signup", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupIn, response: Response) -> SessionOut:
    """Cria o estabelecimento, o usuário dono e já deixa logado."""
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == payload.email)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail já tem conta. Faça login.")

        tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
        set_rls_context(db, tenant_id=tenant_id, user_id=user_id)

        base_slug = slugify(payload.slug or payload.business_name)
        # Com slug escolhido pelo usuário, não inventamos variações: avisamos.
        candidates = [base_slug] if payload.slug else slug_candidates(base_slug)
        tenant = None
        for candidate in candidates:
            try:
                with db.begin_nested():
                    tenant = Tenant(
                        id=tenant_id,
                        name=payload.business_name.strip(),
                        slug=candidate,
                        niche=payload.niche,
                        timezone="America/Sao_Paulo",
                        plan="trial",
                        status="active",
                        trial_ends_at=datetime.now(UTC) + timedelta(days=TRIAL_DAYS),
                    )
                    db.add(tenant)
                    db.flush()
                break
            except IntegrityError:
                # O RLS esconde os outros estabelecimentos, então não dá para
                # consultar se o slug existe; a constraint UNIQUE responde por nós.
                tenant = None
                continue
        if tenant is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Este endereço de link já está em uso. Escolha outro."
            )

        user = User(
            id=user_id,
            email=payload.email,
            name=payload.owner_name.strip(),
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        membership = Membership(tenant_id=tenant_id, user_id=user_id, role=Role.OWNER.value)
        db.add(membership)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Este e-mail já tem conta. Faça login."
            ) from None

        access = _set_auth_cookies(response, user_id, tenant_id)
        return _session_out(db, membership, access)


@router.post("/login", response_model=SessionOut)
def login(payload: LoginIn, response: Response) -> SessionOut:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == payload.email))
        if user is None:
            verify_password(payload.password, DUMMY_PASSWORD_HASH)
            raise _INVALID_LOGIN
        if not verify_password(payload.password, user.password_hash) or not user.is_active:
            raise _INVALID_LOGIN

        set_rls_context(db, user_id=user.id)
        memberships = _user_memberships(db, user.id)
        if not memberships:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Seu usuário não está vinculado a nenhum estabelecimento.",
            )

        if payload.tenant_slug:
            chosen = next((m for m in memberships if m.tenant.slug == payload.tenant_slug), None)
            if chosen is None:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, "Você não tem acesso a este estabelecimento."
                )
        elif len(memberships) == 1:
            chosen = memberships[0]
        else:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "message": "Escolha o estabelecimento (envie tenant_slug).",
                    "tenants": [
                        {"slug": m.tenant.slug, "name": m.tenant.name, "role": m.role}
                        for m in memberships
                    ],
                },
            )

        access = _set_auth_cookies(response, user.id, chosen.tenant_id)
        return _session_out(db, chosen, access)


@router.post("/refresh", response_model=SessionOut)
def refresh(request: Request, response: Response) -> SessionOut:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Faça login.")
    try:
        user_id, tenant_id = decode_token(token, "refresh")
    except InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Faça login.") from None

    with SessionLocal() as db:
        set_rls_context(db, tenant_id=tenant_id, user_id=user_id)
        membership = db.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant_id, Membership.user_id == user_id
            )
        )
        if membership is None or not membership.user.is_active:
            _clear_auth_cookies(response)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Faça login.")
        access = _set_auth_cookies(response, user_id, tenant_id)
        return _session_out(db, membership, access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/switch", response_model=SessionOut)
def switch_tenant(
    payload: SwitchTenantIn,
    response: Response,
    ctx: CurrentContext = Depends(get_current_context),
) -> SessionOut:
    """Troca de estabelecimento para quem trabalha em mais de um."""
    target = next(
        (m for m in _user_memberships(ctx.db, ctx.user.id) if m.tenant.slug == payload.tenant_slug),
        None,
    )
    if target is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Você não tem acesso a este estabelecimento."
        )
    access = _set_auth_cookies(response, ctx.user.id, target.tenant_id)
    return _session_out(ctx.db, target, access)
