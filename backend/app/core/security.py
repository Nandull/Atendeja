import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# Hash fixo usado no login quando o e-mail não existe, para o tempo de resposta
# não revelar quais e-mails estão cadastrados.
DUMMY_PASSWORD_HASH = _hasher.hash("senha-inexistente-para-timing")


def create_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID, token_type: TokenType) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    if token_type == "access":
        expires = now + timedelta(minutes=settings.access_token_minutes)
    else:
        expires = now + timedelta(days=settings.refresh_token_days)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id),
        "typ": token_type,
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class InvalidToken(Exception):
    pass


def decode_token(token: str, expected_type: TokenType) -> tuple[uuid.UUID, uuid.UUID]:
    """Valida o token e devolve (user_id, tenant_id)."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("typ") != expected_type:
            raise InvalidToken("tipo de token incorreto")
        return uuid.UUID(payload["sub"]), uuid.UUID(payload["tid"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidToken(str(exc)) from exc
