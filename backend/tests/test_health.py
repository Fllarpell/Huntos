from fastapi.testclient import TestClient


def test_liveness_does_not_need_auth(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "live"


def test_ready_pings_db(client: TestClient) -> None:
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "ready"}
