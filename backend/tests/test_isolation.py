"""Garante que um estabelecimento nunca enxerga dados de outro.

Testa nas duas camadas: pela API (o que o usuário vê) e direto no banco
(o Row-Level Security bloqueando mesmo sem filtro no código).
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionLocal, engine, set_rls_context
from tests.conftest import make_client, signup


@pytest.fixture
def dois_estabelecimentos():
    ca, cb = make_client(), make_client()
    a = signup(ca, "Clínica A", "dono@a.com")
    b = signup(cb, "Clínica B", "dono@b.com")
    ca.post(
        "/api/v1/members",
        json={
            "name": "Recepção A",
            "email": "rec@a.com",
            "role": "receptionist",
            "password": "senha-forte-123",
        },
    )
    return ca, cb, a, b


def test_usuario_da_api_nao_e_superuser_nem_ignora_rls():
    # Se a API conectar como superusuário, o RLS é ignorado e todo o resto é mentira.
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    assert row.rolsuper is False
    assert row.rolbypassrls is False


def test_api_lista_apenas_equipe_do_proprio_estabelecimento(dois_estabelecimentos):
    ca, cb, _, _ = dois_estabelecimentos
    emails_a = {m["email"] for m in ca.get("/api/v1/members").json()}
    emails_b = {m["email"] for m in cb.get("/api/v1/members").json()}
    assert emails_a == {"dono@a.com", "rec@a.com"}
    assert emails_b == {"dono@b.com"}


def test_api_nao_altera_nem_remove_membro_de_outro_estabelecimento(dois_estabelecimentos):
    ca, cb, _, _ = dois_estabelecimentos
    id_membro_a = ca.get("/api/v1/members").json()[1]["id"]
    assert cb.patch(f"/api/v1/members/{id_membro_a}", json={"role": "admin"}).status_code == 404
    assert cb.delete(f"/api/v1/members/{id_membro_a}").status_code == 404
    assert len(ca.get("/api/v1/members").json()) == 2


def test_banco_sem_contexto_nao_mostra_nada(dois_estabelecimentos):
    with SessionLocal() as db:
        assert db.execute(text("SELECT count(*) FROM tenants")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM memberships")).scalar() == 0


def test_banco_com_contexto_mostra_so_o_tenant_atual(dois_estabelecimentos):
    _, _, a, b = dois_estabelecimentos
    with SessionLocal() as db:
        set_rls_context(db, tenant_id=uuid.UUID(a["tenant"]["id"]))
        # Propositalmente SEM filtro de tenant_id: quem filtra é o banco.
        tenants = db.execute(text("SELECT id FROM tenants")).scalars().all()
        tenant_ids = set(db.execute(text("SELECT tenant_id FROM memberships")).scalars())
    assert [str(t) for t in tenants] == [a["tenant"]["id"]]
    assert {str(t) for t in tenant_ids} == {a["tenant"]["id"]}
    assert b["tenant"]["id"] not in {str(t) for t in tenant_ids}


def test_banco_bloqueia_escrita_em_outro_tenant(dois_estabelecimentos):
    _, _, a, b = dois_estabelecimentos
    with SessionLocal() as db:
        set_rls_context(db, tenant_id=uuid.UUID(a["tenant"]["id"]))
        with pytest.raises(DBAPIError, match="row-level security"):
            db.execute(
                text(
                    "INSERT INTO memberships (id, tenant_id, user_id, role) "
                    "VALUES (:id, :tid, :uid, 'admin')"
                ),
                {"id": uuid.uuid4(), "tid": b["tenant"]["id"], "uid": a["user"]["id"]},
            )


def test_banco_nao_atualiza_linhas_de_outro_tenant(dois_estabelecimentos):
    _, _, a, b = dois_estabelecimentos
    with SessionLocal() as db:
        set_rls_context(db, tenant_id=uuid.UUID(a["tenant"]["id"]))
        result = db.execute(
            text("UPDATE tenants SET name = 'invadido' WHERE id = :id"), {"id": b["tenant"]["id"]}
        )
        db.commit()
    assert result.rowcount == 0


def test_usuario_em_dois_estabelecimentos_escolhe_e_troca(dois_estabelecimentos):
    ca, _, a, b = dois_estabelecimentos
    cb_owner = make_client()
    cb_owner.post("/api/v1/auth/login", json={"email": "dono@b.com", "password": "senha-forte-123"})
    # Dono de B adiciona o dono de A (conta já existente) como admin em B.
    resp = cb_owner.post(
        "/api/v1/members", json={"name": "ignorado", "email": "dono@a.com", "role": "admin"}
    )
    assert resp.status_code == 201

    c = make_client()
    login = c.post(
        "/api/v1/auth/login", json={"email": "dono@a.com", "password": "senha-forte-123"}
    )
    assert login.status_code == 409
    assert {t["slug"] for t in login.json()["detail"]["tenants"]} == {"clinica-a", "clinica-b"}

    login = c.post(
        "/api/v1/auth/login",
        json={"email": "dono@a.com", "password": "senha-forte-123", "tenant_slug": "clinica-b"},
    )
    assert login.status_code == 200
    assert login.json()["role"] == "admin"
    assert {m["email"] for m in c.get("/api/v1/members").json()} == {"dono@b.com", "dono@a.com"}

    switched = c.post("/api/v1/auth/switch", json={"tenant_slug": "clinica-a"})
    assert switched.status_code == 200
    assert c.get("/api/v1/me").json()["tenant"]["slug"] == "clinica-a"
    assert {m["email"] for m in c.get("/api/v1/members").json()} == {"dono@a.com", "rec@a.com"}


def test_troca_para_estabelecimento_sem_acesso_e_negada(dois_estabelecimentos):
    ca, _, _, _ = dois_estabelecimentos
    assert ca.post("/api/v1/auth/switch", json={"tenant_slug": "clinica-b"}).status_code == 403
