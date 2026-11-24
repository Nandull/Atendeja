from tests.conftest import make_client, signup

SENHA = "senha-forte-123"


def _login(email: str):
    c = make_client()
    assert c.post("/api/v1/auth/login", json={"email": email, "password": SENHA}).status_code == 200
    return c


def _add(client, email: str, role: str):
    return client.post(
        "/api/v1/members",
        json={"name": email.split("@")[0], "email": email, "role": role, "password": SENHA},
    )


def test_dono_adiciona_equipe_e_perfis_sao_respeitados(client):
    signup(client, "Clínica A", "dono@a.com")
    assert _add(client, "rec@a.com", "receptionist").status_code == 201
    assert _add(client, "adm@a.com", "admin").status_code == 201

    rec = _login("rec@a.com")
    assert rec.get("/api/v1/members").status_code == 200
    assert _add(rec, "x@a.com", "professional").status_code == 403
    assert rec.patch("/api/v1/tenant", json={"name": "Hack"}).status_code == 403

    adm = _login("adm@a.com")
    assert _add(adm, "pro@a.com", "professional").status_code == 201
    assert _add(adm, "dono2@a.com", "owner").status_code == 403


def test_membro_novo_exige_senha(client):
    signup(client, "Clínica A", "dono@a.com")
    resp = client.post(
        "/api/v1/members", json={"name": "Sem senha", "email": "s@a.com", "role": "admin"}
    )
    assert resp.status_code == 422


def test_membro_duplicado_retorna_409(client):
    signup(client, "Clínica A", "dono@a.com")
    assert _add(client, "rec@a.com", "receptionist").status_code == 201
    assert _add(client, "rec@a.com", "admin").status_code == 409


def test_nao_remove_nem_rebaixa_o_unico_dono(client):
    data = signup(client, "Clínica A", "dono@a.com")
    members = client.get("/api/v1/members").json()
    owner_id = next(m["id"] for m in members if m["user_id"] == data["user"]["id"])
    assert client.delete(f"/api/v1/members/{owner_id}").status_code == 409
    assert client.patch(f"/api/v1/members/{owner_id}", json={"role": "admin"}).status_code == 409


def test_admin_nao_mexe_no_dono(client):
    data = signup(client, "Clínica A", "dono@a.com")
    _add(client, "adm@a.com", "admin")
    owner_id = next(
        m["id"] for m in client.get("/api/v1/members").json() if m["user_id"] == data["user"]["id"]
    )
    adm = _login("adm@a.com")
    assert adm.delete(f"/api/v1/members/{owner_id}").status_code == 403
    assert adm.patch(f"/api/v1/members/{owner_id}", json={"role": "admin"}).status_code == 403


def test_membro_removido_perde_acesso_na_hora(client):
    signup(client, "Clínica A", "dono@a.com")
    rec_id = _add(client, "rec@a.com", "receptionist").json()["id"]
    rec = _login("rec@a.com")
    assert rec.get("/api/v1/me").status_code == 200

    assert client.delete(f"/api/v1/members/{rec_id}").status_code == 204
    # O token dele ainda não venceu, mas o vínculo foi checado no banco.
    assert rec.get("/api/v1/me").status_code == 401


def test_dono_atualiza_dados_do_estabelecimento(client):
    signup(client, "Clínica A", "dono@a.com")
    resp = client.patch(
        "/api/v1/tenant", json={"phone": "21999990000", "timezone": "America/Manaus"}
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "21999990000"
    assert resp.json()["timezone"] == "America/Manaus"
    assert client.patch("/api/v1/tenant", json={"timezone": "Lua/Base"}).status_code == 422
