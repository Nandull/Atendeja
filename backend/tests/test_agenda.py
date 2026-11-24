"""Etapa 3: agenda, conflitos, reagendamento, status, disponibilidade e histórico."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal, set_rls_context
from tests.conftest import make_client, signup

SENHA = "senha-forte-123"
FUTURA = "2030-01-07"  # segunda-feira
PASSADA = "2026-11-16"  # segunda-feira já passada


def at(day: str, hhmm: str) -> str:
    return f"{day}T{hhmm}:00-03:00"


@pytest.fixture
def agenda(client):
    """Clínica com 2 profissionais, expediente seg 08-12 e 13-18, e 1 cliente."""
    data = signup(client, "Clínica A", "dono@a.com")
    limpeza = client.post(
        "/api/v1/services",
        json={
            "name": "Limpeza de pele",
            "duration_min": 60,
            "buffer_min": 15,
            "price_cents": 15000,
        },
    ).json()
    drenagem = client.post(
        "/api/v1/services",
        json={"name": "Drenagem", "duration_min": 30, "price_cents": 9000},
    ).json()
    pros = {}
    for name in ("Carla", "Bia"):
        pid = client.post("/api/v1/professionals", json={"name": name}).json()["id"]
        client.put(
            f"/api/v1/professionals/{pid}/services",
            json=[
                {
                    "service_id": limpeza["id"],
                    "price_cents_override": 17000 if name == "Carla" else None,
                },
                {"service_id": drenagem["id"]},
            ],
        )
        client.put(
            f"/api/v1/professionals/{pid}/working-hours",
            json=[
                {"weekday": 0, "start_time": "08:00", "end_time": "12:00"},
                {"weekday": 0, "start_time": "13:00", "end_time": "18:00"},
            ],
        )
        pros[name] = pid
    maria = client.post("/api/v1/clients", json={"name": "Maria", "phone": "21999990000"}).json()
    return {
        "http": client,
        "tenant": data["tenant"],
        "limpeza": limpeza["id"],
        "drenagem": drenagem["id"],
        "carla": pros["Carla"],
        "bia": pros["Bia"],
        "maria": maria["id"],
    }


def book(ag, starts: str, pro: str = "carla", service: str = "limpeza", http=None, **extra):
    return (http or ag["http"]).post(
        "/api/v1/appointments",
        json={
            "client_id": ag["maria"],
            "professional_id": ag[pro],
            "service_id": ag[service],
            "starts_at": starts,
            **extra,
        },
    )


# --- Criação e conflitos --------------------------------------------------------


def test_agenda_dentro_do_expediente_com_preco_congelado(agenda):
    resp = book(agenda, at(FUTURA, "09:00"))
    assert resp.status_code == 201, resp.text
    a = resp.json()
    assert a["status"] == "scheduled"
    assert a["price_cents"] == 17000  # preço próprio da Carla
    assert a["ends_at"].startswith("2030-01-07T13:00:00")  # 10:00 -03 em UTC
    assert a["blocked_until"].startswith("2030-01-07T13:15:00")  # + 15 min de intervalo
    assert a["client"]["name"] == "Maria"
    assert a["professional"]["name"] == "Carla"

    # Mudar o preço do catálogo depois não altera o agendado.
    agenda["http"].patch(f"/api/v1/services/{agenda['limpeza']}", json={"price_cents": 1})
    again = agenda["http"].get(f"/api/v1/appointments/{a['id']}").json()
    assert again["price_cents"] == 17000


def test_fora_do_expediente_e_encaixe(agenda):
    assert book(agenda, at(FUTURA, "07:00")).status_code == 422
    assert book(agenda, at(FUTURA, "11:30")).status_code == 422  # invade o almoço
    assert book(agenda, at("2030-01-08", "09:00")).status_code == 422  # terça: não atende
    encaixe = book(agenda, at(FUTURA, "07:00"), allow_outside_hours=True)
    assert encaixe.status_code == 201


def test_conflito_considera_intervalo_do_servico(agenda):
    assert book(agenda, at(FUTURA, "09:00")).status_code == 201  # ocupa até 10:15
    conflito = book(agenda, at(FUTURA, "10:00"), service="drenagem")
    assert conflito.status_code == 409
    assert "Maria" in conflito.json()["detail"]
    assert book(agenda, at(FUTURA, "08:45"), service="drenagem").status_code == 409
    assert book(agenda, at(FUTURA, "08:30"), service="drenagem").status_code == 201  # termina 09:00
    assert book(agenda, at(FUTURA, "10:15"), service="drenagem").status_code == 201
    # Outro profissional no mesmo horário: livre.
    assert book(agenda, at(FUTURA, "09:00"), pro="bia").status_code == 201


def test_bloqueio_impede_agendamento(agenda):
    agenda["http"].post(
        "/api/v1/time-blocks",
        json={
            "professional_id": agenda["carla"],
            "starts_at": at(FUTURA, "14:00"),
            "ends_at": at(FUTURA, "15:00"),
            "reason": "Curso",
        },
    )
    resp = book(agenda, at(FUTURA, "13:30"))
    assert resp.status_code == 409
    assert "Curso" in resp.json()["detail"]
    assert book(agenda, at(FUTURA, "13:30"), pro="bia").status_code == 201


def test_servico_que_o_profissional_nao_faz(agenda):
    outro = (
        agenda["http"]
        .post("/api/v1/services", json={"name": "Massagem", "duration_min": 60, "price_cents": 1})
        .json()["id"]
    )
    agenda["massagem"] = outro
    assert book(agenda, at(FUTURA, "09:00"), service="massagem").status_code == 422


def test_banco_barra_sobreposicao_mesmo_sem_a_api(agenda):
    """A trava final é a constraint EXCLUDE: nem um INSERT direto passa."""
    book(agenda, at(FUTURA, "09:00"))
    with SessionLocal() as db:
        set_rls_context(db, tenant_id=uuid.UUID(agenda["tenant"]["id"]))
        with pytest.raises(IntegrityError, match="ex_appointments_no_overlap"):
            db.execute(
                text(
                    "INSERT INTO appointments (id, tenant_id, client_id, professional_id, "
                    "service_id, starts_at, ends_at, blocked_until, price_cents) VALUES "
                    "(:id, :t, :c, :p, :s, :a, :b, :b, 100)"
                ),
                {
                    "id": uuid.uuid4(),
                    "t": agenda["tenant"]["id"],
                    "c": agenda["maria"],
                    "p": agenda["carla"],
                    "s": agenda["drenagem"],
                    "a": at(FUTURA, "09:30"),
                    "b": at(FUTURA, "10:00"),
                },
            )


# --- Reagendar e status ---------------------------------------------------------


def test_reagendar(agenda):
    a = book(agenda, at(FUTURA, "09:00")).json()
    b = book(agenda, at(FUTURA, "14:00")).json()
    http = agenda["http"]

    # Mover 30 min para frente sobrepõe só ele mesmo: permitido.
    moved = http.patch(f"/api/v1/appointments/{a['id']}", json={"starts_at": at(FUTURA, "09:30")})
    assert moved.status_code == 200
    assert moved.json()["starts_at"].startswith("2030-01-07T12:30:00")

    # Para cima de outro atendimento: 409.
    clash = http.patch(f"/api/v1/appointments/{a['id']}", json={"starts_at": at(FUTURA, "14:30")})
    assert clash.status_code == 409

    # Trocar de profissional recalcula o preço (Bia não tem preço próprio).
    bia = http.patch(f"/api/v1/appointments/{b['id']}", json={"professional_id": agenda["bia"]})
    assert bia.json()["professional"]["name"] == "Bia"
    assert bia.json()["price_cents"] == 15000


def test_cancelar_libera_horario_e_e_definitivo(agenda):
    a = book(agenda, at(FUTURA, "09:00")).json()
    http = agenda["http"]
    cancel = http.post(
        f"/api/v1/appointments/{a['id']}/status",
        json={"status": "canceled", "cancel_reason": "Cliente viajou"},
    )
    assert cancel.json()["status"] == "canceled"
    assert cancel.json()["cancel_reason"] == "Cliente viajou"
    assert book(agenda, at(FUTURA, "09:00")).status_code == 201

    volta = http.post(f"/api/v1/appointments/{a['id']}/status", json={"status": "confirmed"})
    assert volta.status_code == 422
    reag = http.patch(f"/api/v1/appointments/{a['id']}", json={"starts_at": at(FUTURA, "15:00")})
    assert reag.status_code == 422


def test_concluir_so_depois_que_comecou(agenda):
    futuro = book(agenda, at(FUTURA, "09:00")).json()
    http = agenda["http"]
    resp = http.post(f"/api/v1/appointments/{futuro['id']}/status", json={"status": "completed"})
    assert resp.status_code == 422

    passado = book(agenda, at(PASSADA, "09:00")).json()
    ok = http.post(f"/api/v1/appointments/{passado['id']}/status", json={"status": "completed"})
    assert ok.json()["status"] == "completed"
    fix = http.post(f"/api/v1/appointments/{passado['id']}/status", json={"status": "no_show"})
    assert fix.json()["status"] == "no_show"


# --- Listagem, disponibilidade e permissões ------------------------------------


def test_lista_por_periodo_e_profissional(agenda):
    book(agenda, at(FUTURA, "09:00"))
    book(agenda, at(FUTURA, "09:00"), pro="bia")
    c = book(agenda, at(FUTURA, "14:00")).json()
    agenda["http"].post(f"/api/v1/appointments/{c['id']}/status", json={"status": "canceled"})
    params = {"start": at(FUTURA, "00:00"), "end": at("2030-01-08", "00:00")}
    http = agenda["http"]
    assert len(http.get("/api/v1/appointments", params=params).json()) == 2
    with_canceled = http.get("/api/v1/appointments", params={**params, "include_canceled": True})
    assert len(with_canceled.json()) == 3
    only_bia = http.get("/api/v1/appointments", params={**params, "professional_id": agenda["bia"]})
    assert [a["professional"]["name"] for a in only_bia.json()] == ["Bia"]


def test_horarios_livres(agenda):
    book(agenda, at(FUTURA, "09:00"))  # limpeza: ocupa 09:00-10:15
    agenda["http"].post(
        "/api/v1/time-blocks",
        json={
            "professional_id": agenda["carla"],
            "starts_at": at(FUTURA, "16:00"),
            "ends_at": at(FUTURA, "18:00"),
        },
    )
    resp = agenda["http"].get(
        "/api/v1/availability",
        params={
            "professional_id": agenda["carla"],
            "service_id": agenda["drenagem"],
            "date": FUTURA,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["duration_min"] == 30
    assert body["slots"][0].endswith("-03:00")  # devolvido no fuso do estabelecimento
    local = [s[11:16] for s in body["slots"]]
    assert local[:4] == ["08:00", "08:15", "08:30", "10:15"]  # 08:45 invadiria 09:00
    assert "11:30" in local and "11:45" not in local  # cabe até 12:00
    assert "12:00" not in local and "13:00" in local  # almoço
    assert "15:30" in local and "15:45" not in local  # bloqueio às 16:00

    passado = agenda["http"].get(
        "/api/v1/availability",
        params={
            "professional_id": agenda["carla"],
            "service_id": agenda["drenagem"],
            "date": PASSADA,
        },
    )
    assert passado.json()["slots"] == []


def test_profissional_ve_e_mexe_so_na_propria_agenda(agenda):
    http = agenda["http"]
    member = http.post(
        "/api/v1/members",
        json={"name": "Carla", "email": "carla@a.com", "role": "professional", "password": SENHA},
    ).json()
    http.patch(f"/api/v1/professionals/{agenda['carla']}", json={"user_id": member["user_id"]})
    book(agenda, at(FUTURA, "09:00"))
    da_bia = book(agenda, at(FUTURA, "09:00"), pro="bia").json()

    carla = make_client()
    carla.post("/api/v1/auth/login", json={"email": "carla@a.com", "password": SENHA})
    params = {"start": at(FUTURA, "00:00"), "end": at("2030-01-08", "00:00")}
    assert [
        a["professional"]["name"] for a in carla.get("/api/v1/appointments", params=params).json()
    ] == ["Carla"]
    assert carla.get(f"/api/v1/appointments/{da_bia['id']}").status_code == 403
    cancel = carla.post(f"/api/v1/appointments/{da_bia['id']}/status", json={"status": "canceled"})
    assert cancel.status_code == 403
    assert book(agenda, at(FUTURA, "14:00"), pro="bia", http=carla).status_code == 403
    assert book(agenda, at(FUTURA, "14:00"), http=carla).status_code == 201
    assert (
        book(agenda, at(FUTURA, "07:00"), http=carla, allow_outside_hours=True).status_code == 403
    )


# --- Histórico do cliente e isolamento -------------------------------------------


def test_historico_e_frequencia_do_cliente(agenda):
    http = agenda["http"]
    ids = [
        book(agenda, at(day, "09:00")).json()["id"] for day in ("2026-11-02", "2026-11-09", PASSADA)
    ]
    for i in ids[:2]:
        http.post(f"/api/v1/appointments/{i}/status", json={"status": "completed"})
    http.post(f"/api/v1/appointments/{ids[2]}/status", json={"status": "no_show"})
    book(agenda, at(FUTURA, "09:00"))

    hist = http.get(f"/api/v1/clients/{agenda['maria']}/history").json()
    st = hist["stats"]
    assert st["completed"] == 2
    assert st["no_show"] == 1
    assert st["upcoming"] == 1
    assert st["total_spent_cents"] == 34000
    assert st["avg_days_between_visits"] == 7.0
    assert len(hist["appointments"]) == 4
    assert hist["appointments"][0]["starts_at"].startswith("2030")  # mais recente primeiro


def test_agenda_isolada_entre_estabelecimentos(agenda):
    a = book(agenda, at(FUTURA, "09:00")).json()
    b = make_client()
    signup(b, "Clínica B", "dono@b.com")
    params = {"start": at(FUTURA, "00:00"), "end": at("2030-01-08", "00:00")}
    assert b.get("/api/v1/appointments", params=params).json() == []
    assert b.get(f"/api/v1/appointments/{a['id']}").status_code == 404
    assert (
        b.post(f"/api/v1/appointments/{a['id']}/status", json={"status": "canceled"}).status_code
        == 404
    )
    # B não consegue agendar usando cliente/profissional de A.
    assert book(agenda, at(FUTURA, "10:30"), http=b).status_code == 404
    assert b.get(f"/api/v1/clients/{agenda['maria']}/history").status_code == 404
