from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import login


def test_gateway_lifecycle(client: TestClient):
    login(client, "admin", "admin-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Gateway Space"}).json()["id"]

    start_response = client.post(f"/api/workspaces/{workspace_id}/gateway/start")
    assert start_response.status_code == 200
    assert start_response.json()["state"] == "running"

    status_response = client.get(f"/api/workspaces/{workspace_id}/gateway/status")
    assert status_response.status_code == 200
    assert status_response.json()["state"] == "running"

    stop_response = client.post(f"/api/workspaces/{workspace_id}/gateway/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["state"] == "stopped"
