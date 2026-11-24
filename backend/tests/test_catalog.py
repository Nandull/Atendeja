"""Etapa 2: serviços, profissionais, expediente, bloqueios e clientes."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal, set_rls_context
from tests.conftest import make_client, signup

SENHA = "senha-forte-123"
LIMPEZA = {"name": "Limpeza de pele", "duration_min": 60, "price_cents": 15000}
DRENAGEM = {"name": "Drenagem linfática", "duration_min": 50, "price_cents": 12000}


@pytest.fixture
def dono(client):
    signup(client, "Clínica A", "dono@a.com")
    return client


def _login(email: str):
    c = make_client()
    assert c.post("/api/v1/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return c


def _member(owner, email: str, role: str) -> dict:
    resp = owner.post(
        "/api/v1/members",
        json={"name": email.split("@")[0], "email": email, "role": role, "password": SENHA},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Serviços -----------------------------------------------------------------


def test_crud_de_servico(dono):
    created = dono.post("/api/v1/services", json={**LIMPEZA, "buffer_min": 10})
    assert created.status_code == 201
    sid = created.json()["id"]
    assert created.json()["buffer_min"] == 10
    assert created.json()["online_booking"] is True

    upd = dono.patch(f"/api/v1/services/{sid}", json={"price_cents": 18000})
    assert upd.json()["price_cents"] == 18000
    assert upd.json()["name"] == "Limpeza de pele"

    dono.patch(f"/api/v1/services/{sid}", json={"active": False})
    assert dono.get("/api/v1/services").json() == []
    assert len(dono.get("/api/v1/services?include_inactive=true").json()) == 1


def test_servico_com_nome_repetido_ignora_maiusculas(dono):
    dono.post("/api/v1/services", json=LIMPEZA)
    dup = dono.post("/api/v1/services", json={**LIMPEZA, "name": "LIMPEZA DE PELE"})
    assert dup.status_code == 409


def test_servico_valida_duracao_e_preco(dono):
    assert dono.post("/api/v1/services", json={**LIMPEZA, "duration_min": 2}).status_code == 422
    assert dono.post("/api/v1/services", json={**LIMPEZA, "price_cents": -1}).status_code == 422


def test_recepcao_ve_mas_nao_cria_servico(dono):
    _member(dono, "rec@a.com", "receptionist")
    rec = _login("rec@a.com")
    dono.post("/api/v1/services", json=LIMPEZA)
    assert len(rec.get("/api/v1/services").json()) == 1
    assert rec.post("/api/v1/services", json=DRENAGEM).status_code == 403


# --- Profissionais ------------------------------------------------------------


def test_profissional_com_servicos_e_preco_proprio(dono):
    s1 = dono.post("/api/v1/services", json=LIMPEZA).json()["id"]
    s2 = dono.post("/api/v1/services", json=DRENAGEM).json()["id"]
    p = dono.post(
        "/api/v1/professionals",
        json={"name": "Carla", "specialty": "Esteticista", "service_ids": [s1]},
    )
    assert p.status_code == 201
    pid = p.json()["id"]
    assert [s["name"] for s in p.json()["services"]] == ["Limpeza de pele"]

    resp = dono.put(
        f"/api/v1/professionals/{pid}/services",
        json=[{"service_id": s1, "price_cents_override": 20000}, {"service_id": s2}],
    )
    assert resp.status_code == 200
    by_name = {s["name"]: s for s in resp.json()["services"]}
    assert by_name["Limpeza de pele"]["price_cents"] == 20000
    assert by_name["Drenagem linfática"]["price_cents"] == 12000
    assert by_name["Drenagem linfática"]["price_cents_override"] is None


def test_profissional_ligado_a_usuario_da_equipe(dono):
    member = _member(dono, "carla@a.com", "professional")
    ok = dono.post("/api/v1/professionals", json={"name": "Carla", "user_id": member["user_id"]})
    assert ok.status_code == 201
    dup = dono.post("/api/v1/professionals", json={"name": "Outra", "user_id": member["user_id"]})
    assert dup.status_code == 409
    estranho = dono.post("/api/v1/professionals", json={"name": "X", "user_id": str(uuid.uuid4())})
    assert estranho.status_code == 422


def test_expediente_com_varias_faixas_e_sem_sobreposicao(dono):
    pid = dono.post("/api/v1/professionals", json={"name": "Carla"}).json()["id"]
    semana = [
        {"weekday": 0, "start_time": "13:00", "end_time": "18:00"},
        {"weekday": 0, "start_time": "08:00", "end_time": "12:00"},
        {"weekday": 5, "start_time": "08:00", "end_time": "12:00"},
    ]
    resp = dono.put(f"/api/v1/professionals/{pid}/working-hours", json=semana)
    assert resp.status_code == 200
    assert [(h["weekday"], h["start_time"]) for h in resp.json()] == [
        (0, "08:00:00"),
        (0, "13:00:00"),
        (5, "08:00:00"),
    ]

    sobreposto = [
        {"weekday": 1, "start_time": "08:00", "end_time": "12:00"},
        {"weekday": 1, "start_time": "11:00", "end_time": "15:00"},
    ]
    assert (
        dono.put(f"/api/v1/professionals/{pid}/working-hours", json=sobreposto).status_code == 422
    )
    invertido = [{"weekday": 1, "start_time": "12:00", "end_time": "08:00"}]
    assert dono.put(f"/api/v1/professionals/{pid}/working-hours", json=invertido).status_code == 422

    # Substitui tudo: a lista vazia limpa o expediente.
    assert dono.put(f"/api/v1/professionals/{pid}/working-hours", json=[]).json() == []


# --- Bloqueios ----------------------------------------------------------------


def test_bloqueios_por_periodo_e_do_estabelecimento(dono):
    pid = dono.post("/api/v1/professionals", json={"name": "Carla"}).json()["id"]
    outro = dono.post("/api/v1/professionals", json={"name": "Bia"}).json()["id"]
    dono.post(
        "/api/v1/time-blocks",
        json={
            "professional_id": pid,
            "starts_at": "2026-12-10T12:00:00-03:00",
            "ends_at": "2026-12-10T13:00:00-03:00",
            "reason": "Médico",
        },
    )
    dono.post(
        "/api/v1/time-blocks",
        json={
            "starts_at": "2026-12-25T00:00:00-03:00",
            "ends_at": "2026-12-26T00:00:00-03:00",
            "reason": "Natal",
        },
    )
    dono.post(
        "/api/v1/time-blocks",
        json={
            "professional_id": outro,
            "starts_at": "2026-12-11T09:00:00-03:00",
            "ends_at": "2026-12-11T10:00:00-03:00",
        },
    )
    params = {"start": "2026-12-01T00:00:00-03:00", "end": "2027-01-01T00:00:00-03:00"}
    assert len(dono.get("/api/v1/time-blocks", params=params).json()) == 3
    da_carla = dono.get("/api/v1/time-blocks", params={**params, "professional_id": pid}).json()
    assert {b["reason"] for b in da_carla} == {"Médico", "Natal"}

    sem_fuso = dono.post(
        "/api/v1/time-blocks",
        json={"starts_at": "2026-12-10T12:00:00", "ends_at": "2026-12-10T13:00:00"},
    )
    assert sem_fuso.status_code == 422


def test_profissional_so_bloqueia_a_propria_agenda(dono):
    member = _member(dono, "carla@a.com", "professional")
    carla = dono.post(
        "/api/v1/professionals", json={"name": "Carla", "user_id": member["user_id"]}
    ).json()["id"]
    bia = dono.post("/api/v1/professionals", json={"name": "Bia"}).json()["id"]
    c = _login("carla@a.com")
    periodo = {"starts_at": "2026-12-10T12:00:00Z", "ends_at": "2026-12-10T13:00:00Z"}

    assert (
        c.post("/api/v1/time-blocks", json={**periodo, "professional_id": carla}).status_code == 201
    )
    assert (
        c.post("/api/v1/time-blocks", json={**periodo, "professional_id": bia}).status_code == 403
    )
    assert c.post("/api/v1/time-blocks", json=periodo).status_code == 403

    rec_block = dono.post("/api/v1/time-blocks", json={**periodo, "professional_id": bia}).json()
    assert c.delete(f"/api/v1/time-blocks/{rec_block['id']}").status_code == 403
    assert dono.delete(f"/api/v1/time-blocks/{rec_block['id']}").status_code == 204


# --- Clientes -----------------------------------------------------------------


def test_cliente_telefone_normalizado_e_unico(dono):
    c = dono.post("/api/v1/clients", json={"name": "José da Silva", "phone": "+55 (21) 99999-0000"})
    assert c.status_code == 201
    assert c.json()["phone"] == "21999990000"

    dup = dono.post("/api/v1/clients", json={"name": "Outro", "phone": "21 99999 0000"})
    assert dup.status_code == 409
    assert dup.json()["detail"]["name"] == "José da Silva"

    assert dono.post("/api/v1/clients", json={"name": "X", "phone": "1234"}).status_code == 422


def test_busca_de_clientes_por_nome_sem_acento_e_telefone(dono):
    for name, phone in [
        ("José da Silva", "21999990000"),
        ("Ana Lúcia", "21988887777"),
        ("Joana Prado", "11977776666"),
    ]:
        dono.post("/api/v1/clients", json={"name": name, "phone": phone})

    def busca(q):
        return [c["name"] for c in dono.get("/api/v1/clients", params={"q": q}).json()["items"]]

    assert busca("jose") == ["José da Silva"]
    assert busca("LUCIA") == ["Ana Lúcia"]
    assert busca("jo") == ["Joana Prado", "José da Silva"]
    assert busca("8888") == ["Ana Lúcia"]
    assert busca("(11) 9777") == ["Joana Prado"]
    assert busca("100%") == []

    page = dono.get("/api/v1/clients", params={"limit": 2}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2


def test_editar_cliente_atualiza_busca(dono):
    cid = dono.post("/api/v1/clients", json={"name": "Maria", "phone": "21999990000"}).json()["id"]
    dono.patch(f"/api/v1/clients/{cid}", json={"name": "Mariângela", "notes": "Pele sensível"})
    items = dono.get("/api/v1/clients", params={"q": "mariangela"}).json()["items"]
    assert items[0]["notes"] == "Pele sensível"


# --- Isolamento das novas tabelas ---------------------------------------------


def test_cadastros_isolados_entre_estabelecimentos(dono):
    sid = dono.post("/api/v1/services", json=LIMPEZA).json()["id"]
    pid = dono.post("/api/v1/professionals", json={"name": "Carla"}).json()["id"]
    cid = dono.post("/api/v1/clients", json={"name": "Maria", "phone": "21999990000"}).json()["id"]

    b = make_client()
    signup(b, "Clínica B", "dono@b.com")
    assert b.get("/api/v1/services").json() == []
    assert b.get("/api/v1/professionals").json() == []
    assert b.get("/api/v1/clients").json()["total"] == 0
    assert b.get(f"/api/v1/services/{sid}").status_code == 404
    assert b.get(f"/api/v1/professionals/{pid}").status_code == 404
    assert b.get(f"/api/v1/clients/{cid}").status_code == 404
    assert b.patch(f"/api/v1/clients/{cid}", json={"name": "Hack"}).status_code == 404
    # B não consegue usar o serviço de A num profissional seu.
    resp = b.post("/api/v1/professionals", json={"name": "Bia", "service_ids": [sid]})
    assert resp.status_code == 422
    # O mesmo telefone pode existir como cliente em outro estabelecimento.
    assert (
        b.post("/api/v1/clients", json={"name": "Maria", "phone": "21999990000"}).status_code == 201
    )


def test_banco_impede_ligar_servico_de_outro_tenant(dono):
    """Mesmo passando pela API, a FK composta (tenant_id, id) barra a referência."""
    sid_a = dono.post("/api/v1/services", json=LIMPEZA).json()["id"]
    b = make_client()
    data_b = signup(b, "Clínica B", "dono@b.com")
    pid_b = b.post("/api/v1/professionals", json={"name": "Bia"}).json()["id"]

    with SessionLocal() as db:
        set_rls_context(db, tenant_id=uuid.UUID(data_b["tenant"]["id"]))
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO professional_services (tenant_id, professional_id, service_id) "
                    "VALUES (:t, :p, :s)"
                ),
                {"t": data_b["tenant"]["id"], "p": pid_b, "s": sid_a},
            )


@pytest.mark.parametrize(
    "table",
    [
        "services",
        "professionals",
        "professional_services",
        "working_hours",
        "time_blocks",
        "clients",
    ],
)
def test_rls_ativo_e_forcado_nas_novas_tabelas(table):
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :t"),
            {"t": table},
        ).one()
    assert row.relrowsecurity and row.relforcerowsecurity
