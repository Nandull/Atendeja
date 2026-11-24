from tests.conftest import make_client, signup


def test_signup_cria_estabelecimento_e_loga(client):
    data = signup(client, "Clínica Bella Estética", "ana@bella.com")
    assert data["tenant"]["slug"] == "clinica-bella-estetica"
    assert data["tenant"]["niche"] == "estetica"
    assert data["tenant"]["plan"] == "trial"
    assert data["role"] == "owner"
    assert "access_token" in client.cookies

    me = client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "ana@bella.com"
    assert me.json()["access_token"] is None


def test_email_normalizado_e_duplicado_bloqueado(client):
    signup(client, "Clínica A", "Ana@Bella.com")
    resp = make_client().post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Clínica B",
            "owner_name": "Outra",
            "email": "ana@bella.com",
            "password": "senha-forte-123",
        },
    )
    assert resp.status_code == 409


def test_slug_repetido_ganha_sufixo():
    a = signup(make_client(), "Studio Pele", "a@x.com")
    b = signup(make_client(), "Studio Pele", "b@x.com")
    assert a["tenant"]["slug"] == "studio-pele"
    assert b["tenant"]["slug"] == "studio-pele-2"


def test_slug_escolhido_ja_em_uso_retorna_409():
    signup(make_client(), "Studio Pele", "a@x.com", slug="studio-pele")
    resp = make_client().post(
        "/api/v1/auth/signup",
        json={
            "business_name": "Outro",
            "owner_name": "Outra",
            "email": "b@x.com",
            "password": "senha-forte-123",
            "slug": "studio-pele",
        },
    )
    assert resp.status_code == 409


def test_nicho_invalido_retorna_422(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": "X",
            "owner_name": "Y",
            "email": "x@y.com",
            "password": "senha-forte-123",
            "niche": "padaria",
        },
    )
    assert resp.status_code == 422


def test_login_senha_errada_e_email_inexistente(client):
    signup(make_client(), "Clínica A", "ana@a.com")
    wrong = client.post("/api/v1/auth/login", json={"email": "ana@a.com", "password": "errada"})
    unknown = client.post("/api/v1/auth/login", json={"email": "zz@a.com", "password": "errada"})
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_login_refresh_logout(client):
    signup(make_client(), "Clínica A", "ana@a.com")
    resp = client.post(
        "/api/v1/auth/login", json={"email": "ANA@a.com", "password": "senha-forte-123"}
    )
    assert resp.status_code == 200
    assert client.get("/api/v1/me").status_code == 200

    assert client.post("/api/v1/auth/refresh").status_code == 200

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").status_code == 401


def test_token_bearer_funciona_sem_cookie():
    data = signup(make_client(), "Clínica A", "ana@a.com")
    fresh = make_client()
    resp = fresh.get("/api/v1/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert resp.status_code == 200


def test_sem_token_ou_token_invalido_retorna_401(client):
    assert client.get("/api/v1/me").status_code == 401
    resp = client.get("/api/v1/me", headers={"Authorization": "Bearer lixo"})
    assert resp.status_code == 401


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
