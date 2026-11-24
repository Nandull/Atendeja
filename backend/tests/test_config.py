import pytest

from app.core.config import Settings


def test_producao_exige_segredo_forte_e_cookie_seguro():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="production", jwt_secret="curta", cookie_secure=True)
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(environment="production", jwt_secret="x" * 40, cookie_secure=False)
    ok = Settings(environment="production", jwt_secret="x" * 40, cookie_secure=True)
    assert ok.cookie_secure is True
