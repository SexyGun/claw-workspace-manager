from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import login


def test_workspace_runtime_lifecycle(client: TestClient):
    login(client, "admin", "admin-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Gateway Space"}).json()["id"]

    start_response = client.post(f"/api/workspaces/{workspace_id}/runtime/start")
    assert start_response.status_code == 200
    assert start_response.json()["state"] == "running"
    assert start_response.json()["unit_name"] == f"claw-nanobot@{workspace_id}.service"

    status_response = client.get(f"/api/workspaces/{workspace_id}/runtime")
    assert status_response.status_code == 200
    assert status_response.json()["state"] == "running"
    assert status_response.json()["listen_port"] == 18080

    stop_response = client.post(f"/api/workspaces/{workspace_id}/runtime/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["state"] == "stopped"
