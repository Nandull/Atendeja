"""Etapa 4: página pública de agendamento (sem login)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.config import get_settings
from tests.conftest import make_client, signup

TZ = ZoneInfo("America/Sao_Paulo")
ALL_WEEK = [
    {"weekday": d, "start_time": s, "end_time": e}
    for d in range(7)
    for s, e in (("08:00", "12:00"), ("13:00", "18:00"))
]


def dia(offset: int) -> str:
    return (datetime.now(TZ).date() + timedelta(days=offset)).isoformat()


def at(day: str, hhmm: str) -> str:
    return f"{day}T{hhmm}:00-03:00"


@pytest.fixture
def clinica(client):
    """Clínica com 2 profissionais atendendo todos os dias, 1 serviço online e 1 interno."""
    data = signup(client, "Clínica Bella", "dono@bella.com", slug="clinica-bella")
    client.patch(
        "/api/v1/tenant",
        json={"phone": "21999998888", "booking_note": "Chegue 10 min antes."},
    )
    limpeza = client.post(
        "/api/v1/services",
        json={"name": "Limpeza de pele", "duration_min": 60, "buffer_min": 15,
              "price_cents": 15000},
    ).json()  # fmt: skip
    interno = client.post(
        "/api/v1/services",
        json={"name": "Avaliação interna", "duration_min": 30, "price_cents": 0,
              "online_booking": False},
    ).json()  # fmt: skip
    pros = {}
    for name in ("Ana", "Bia"):
        pid = client.post("/api/v1/professionals", json={"name": name}).json()["id"]
        client.put(
            f"/api/v1/professionals/{pid}/services",
            json=[
                {"service_id": limpeza["id"],
                 "price_cents_override": 18000 if name == "Bia" else None},
                {"service_id": interno["id"]},
            ],
        )  # fmt: skip
        client.put(f"/api/v1/professionals/{pid}/working-hours", json=ALL_WEEK)
        pros[name] = pid
    return {"http": client, "tenant": data["tenant"], "limpeza": limpeza["id"],
            "interno": interno["id"], **pros}  # fmt: skip


def reservar(c, starts: str, phone: str = "21988887777", name: str = "Joana", **extra):
    body = {"service_id": c["limpeza"], "starts_at": starts, "name": name, "phone": phone}
    return make_client().post("/api/v1/public/clinica-bella/appointments", json={**body, **extra})


def test_pagina_mostra_so_servicos_online_e_campos_publicos(clinica):
    anon = make_client()
    resp = anon.get("/api/v1/public/clinica-bella")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Clínica Bella"
    assert body["note"] == "Chegue 10 min antes."
    assert [s["name"] for s in body["services"]] == ["Limpeza de pele"]
    servico = body["services"][0]
    assert servico["price_cents"] == 15000 and servico["price_varies"] is True
    assert {p["name"]: p["price_cents"] for p in servico["professionals"]} == {
        "Ana": 15000,
        "Bia": 18000,
    }
    # Nada de plano, id do estabelecimento, e-mails ou dados internos.
    for campo in ("id", "plan", "status", "trial_ends_at"):
        assert campo not in body


def test_slug_inexistente_ou_desligado_da_404(clinica):
    anon = make_client()
    assert anon.get("/api/v1/public/nao-existe").status_code == 404
    assert anon.get("/api/v1/public/Clinica_Bella").status_code == 422
    clinica["http"].patch("/api/v1/tenant", json={"booking_enabled": False})
    assert anon.get("/api/v1/public/clinica-bella").status_code == 404
    clinica["http"].patch("/api/v1/tenant", json={"booking_enabled": True})
    assert anon.get("/api/v1/public/clinica-bella").status_code == 200


def test_link_de_um_estabelecimento_nao_ve_outro(clinica):
    outro = make_client()
    signup(outro, "Studio Rival", "dono@rival.com", slug="studio-rival")
    outro.post("/api/v1/services", json={"name": "Secreto", "duration_min": 30, "price_cents": 1})
    rival = make_client().get("/api/v1/public/studio-rival").json()
    assert rival["services"] == []  # sem profissional, nada é agendável
    bella = make_client().get("/api/v1/public/clinica-bella").json()
    assert "Secreto" not in [s["name"] for s in bella["services"]]
    # Serviço de outro estabelecimento não é aceito pelo link da Bella.
    resp = make_client().get(
        "/api/v1/public/clinica-bella/availability",
        params={"service_id": rival["services"][0]["id"] if rival["services"] else
                "00000000-0000-0000-0000-000000000000"},
    )  # fmt: skip
    assert resp.status_code == 422


def test_disponibilidade_respeita_antecedencia_janela_e_servico_interno(clinica):
    anon = make_client()
    url = "/api/v1/public/clinica-bella/availability"
    resp = anon.get(url, params={"service_id": clinica["limpeza"], "days": 7})
    assert resp.status_code == 200, resp.text
    days = resp.json()["days"]
    assert len(days) == 7
    limite = datetime.now(UTC) + timedelta(minutes=120)
    for d in days:
        for s in d["slots"]:
            assert datetime.fromisoformat(s["starts_at"]) >= limite
    amanha = days[1]["slots"]
    assert amanha[0]["starts_at"].endswith("08:00:00-03:00")
    # Serviço de 60 min: último início da manhã às 11:00, da tarde às 17:00.
    horas = {s["starts_at"][11:16] for s in amanha}
    assert "11:00" in horas and "11:15" not in horas and "17:00" in horas
    # Serviço que não é online não aparece.
    assert anon.get(url, params={"service_id": clinica["interno"]}).status_code == 422
    # Janela padrão de 30 dias: nada além disso.
    longe = anon.get(url, params={"service_id": clinica["limpeza"], "start": dia(40)})
    assert longe.json()["days"] == []


def test_cliente_agenda_sem_login_e_aparece_na_agenda_interna(clinica):
    day = dia(2)
    resp = reservar(clinica, at(day, "09:00"), professional_id=clinica["Bia"],
                    email="Joana@Mail.com ", notes="Pele sensível")  # fmt: skip
    assert resp.status_code == 201, resp.text
    conf = resp.json()
    assert conf["professional"] == "Bia" and conf["price_cents"] == 18000
    assert conf["business_phone"] == "21999998888"

    agenda = (
        clinica["http"]
        .get("/api/v1/appointments", params={"start": at(day, "00:00"), "end": at(day, "23:59")})
        .json()
    )
    assert len(agenda) == 1
    a = agenda[0]
    assert a["origin"] == "online" and a["status"] == "scheduled"
    assert a["client"]["name"] == "Joana" and a["notes"] == "Pele sensível"
    clientes = clinica["http"].get("/api/v1/clients", params={"q": "joana"}).json()["items"]
    assert clientes[0]["email"] == "joana@mail.com"


def test_horario_ocupado_nao_aparece_e_nao_aceita_duplo(clinica):
    day = dia(2)
    assert reservar(clinica, at(day, "09:00"), professional_id=clinica["Ana"]).status_code == 201
    # Mesmo horário com a Ana: recusado.
    dup = reservar(clinica, at(day, "09:30"), phone="21977776666", professional_id=clinica["Ana"])
    assert dup.status_code == 409
    # Sem preferência: o sistema escolhe quem está livre (Bia).
    livre = reservar(clinica, at(day, "09:00"), phone="21977776666")
    assert livre.status_code == 201 and livre.json()["professional"] == "Bia"
    # Agora 09:00 sumiu da lista "sem preferência".
    days = (
        make_client()
        .get(
            "/api/v1/public/clinica-bella/availability",
            params={"service_id": clinica["limpeza"], "start": day, "days": 1},
        )
        .json()["days"]
    )
    horas = {s["starts_at"][11:16] for s in days[0]["slots"]}
    assert "09:00" not in horas and "10:15" in horas  # 60 min + 15 de intervalo
    # Terceira pessoa às 09:00 sem preferência: ninguém livre.
    assert reservar(clinica, at(day, "09:00"), phone="21966665555").status_code == 409


def test_cliente_existente_nao_tem_nome_trocado(clinica):
    clinica["http"].post("/api/v1/clients", json={"name": "Maria Souza", "phone": "21955554444"})
    resp = reservar(clinica, at(dia(3), "14:00"), phone="(21) 95555-4444", name="Outro Nome")
    assert resp.status_code == 201, resp.text
    clientes = clinica["http"].get("/api/v1/clients", params={"q": "21955554444"}).json()["items"]
    assert len(clientes) == 1 and clientes[0]["name"] == "Maria Souza"


@pytest.mark.parametrize(
    ("hora", "offset", "extra", "esperado"),
    [
        ("09:07", 2, {}, 422),  # fora da grade de 15 min
        ("07:00", 2, {}, 409),  # fora do expediente
        ("09:00", 45, {}, 422),  # além da janela de 30 dias
        ("09:00", 2, {"website": "http://spam"}, 422),  # robô caiu na armadilha
        ("09:00", 2, {"phone": "123"}, 422),  # telefone inválido
    ],
)
def test_validacoes_do_agendamento(clinica, hora, offset, extra, esperado):
    assert reservar(clinica, at(dia(offset), hora), **extra).status_code == esperado


def test_antecedencia_minima(clinica):
    clinica["http"].patch("/api/v1/tenant", json={"booking_min_notice_min": 60 * 24 * 3})
    assert reservar(clinica, at(dia(1), "10:00")).status_code == 422
    assert reservar(clinica, at(dia(5), "10:00")).status_code == 201


def test_limite_de_agendamentos_em_aberto_por_telefone(clinica):
    limite = get_settings().public_max_open_per_phone
    for i in range(limite):
        assert reservar(clinica, at(dia(2 + i), "10:00")).status_code == 201
    resp = reservar(clinica, at(dia(10), "10:00"))
    assert resp.status_code == 422 and "fale com o estabelecimento" in resp.json()["detail"]


def test_limite_de_tentativas_por_ip(clinica, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_booking_per_hour", 2)
    codes = [reservar(clinica, at(dia(2), "08:00"), phone=f"2198888000{i}").status_code
             for i in range(3)]  # fmt: skip
    assert codes[-1] == 429


def test_configuracao_do_agendamento_online(clinica):
    http = clinica["http"]
    resp = http.patch(
        "/api/v1/tenant", json={"booking_window_days": 7, "booking_min_notice_min": 0}
    )
    assert resp.status_code == 200 and resp.json()["booking_window_days"] == 7
    assert http.patch("/api/v1/tenant", json={"booking_window_days": 0}).status_code == 422
    assert http.patch("/api/v1/tenant", json={"booking_enabled": None}).status_code == 200
    assert http.get("/api/v1/tenant").json()["booking_enabled"] is True


def test_slug_reservado_no_cadastro(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={"business_name": "Agenda", "owner_name": "Fulano", "email": "f@x.com",
              "password": "senha-forte-123", "slug": "agenda"},
    )  # fmt: skip
    assert resp.status_code == 409
    auto = make_client()
    data = signup(auto, "Agenda", "g@x.com")
    assert data["tenant"]["slug"] == "agenda-2"
