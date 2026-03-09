from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import login


def test_workspace_creation_renders_configs(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    client.post("/api/users", json={"username": "alice", "password": "alice-password", "role": "user", "is_active": True})
    client.post("/api/auth/logout")
    login(client, "alice", "alice-password")

    create_response = client.post("/api/workspaces", json={"name": "Alice Primary"})
    assert create_response.status_code == 201, create_response.text
    workspace = create_response.json()

    detail_response = client.get(f"/api/workspaces/{workspace['id']}")
    assert detail_response.status_code == 200

    local_root = Path(app_env["workspaces_local"])
    config_path = local_root / "2" / "alice-primary" / ".nanobot" / "config.json"
    gateway_path = local_root / "2" / "alice-primary" / ".nanobot" / "gateway.yaml"
    assert config_path.exists()
    assert gateway_path.exists()

    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert config_payload["workspace"]["slug"] == "alice-primary"
    assert "feishu" in config_payload["channels"]


def test_workspace_access_isolation(client: TestClient):
    login(client, "admin", "admin-password")
    client.post("/api/users", json={"username": "alice", "password": "alice-password", "role": "user", "is_active": True})
    client.post("/api/users", json={"username": "bob", "password": "bob-password-1", "role": "user", "is_active": True})

    client.post("/api/auth/logout")
    login(client, "alice", "alice-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Private Space"}).json()["id"]

    client.post("/api/auth/logout")
    login(client, "bob", "bob-password-1")
    response = client.get(f"/api/workspaces/{workspace_id}")
    assert response.status_code == 403
