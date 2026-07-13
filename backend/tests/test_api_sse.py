import uuid


def _register_and_login(client) -> str:
    email = f"sse-test-{uuid.uuid4().hex[:12]}@example.com"
    resp = client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    return resp.json()["access_token"]


def test_insights_query_streams_sse_frames(client):
    token = _register_and_login(client)
    resp = client.post(
        "/insights/query",
        json={"query": "clients with account balance greater than 1 million from city xyz"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    body = resp.text
    # No real Azure OpenAI credentials in the test environment, so the
    # pipeline is expected to fail gracefully inside the graph rather than
    # crash the HTTP response -- verifying the safe error/done frames still
    # ride over a well-formed SSE stream is the point of this test.
    assert "event: session" in body
    assert "event: done" in body
