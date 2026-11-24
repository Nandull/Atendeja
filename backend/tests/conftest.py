import os

# Os testes rodam num banco separado. Precisa ser definido ANTES de importar o app.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://atendeja:atendeja@localhost:5432/atendeja_test"
)
os.environ.setdefault("JWT_SECRET", "chave-de-teste-com-mais-de-32-bytes-ok")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    from app.core.ratelimit import limiter

    limiter.reset()
    yield
    # TRUNCATE não passa pelo RLS, então limpa tudo entre um teste e outro.
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE tenants, users CASCADE"))


def make_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return make_client()


def signup(client: TestClient, business: str, email: str, **extra) -> dict:
    payload = {
        "business_name": business,
        "owner_name": "Dono " + business,
        "email": email,
        "password": "senha-forte-123",
        **extra,
    }
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()
