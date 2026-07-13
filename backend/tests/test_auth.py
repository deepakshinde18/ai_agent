import uuid


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


def test_register_then_login(client):
    email = _unique_email()
    register_resp = client.post(
        "/auth/register", json={"email": email, "password": "supersecret123"}
    )
    assert register_resp.status_code == 201
    assert "access_token" in register_resp.json()

    login_resp = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


def test_register_duplicate_email_rejected(client):
    email = _unique_email()
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    resp = client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    assert resp.status_code == 409


def test_login_wrong_password_rejected(client):
    email = _unique_email()
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    resp = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert resp.status_code == 401


def test_insights_query_requires_auth(client):
    resp = client.post("/insights/query", json={"query": "clients in city xyz"})
    assert resp.status_code == 401


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
