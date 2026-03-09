from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import app.config
from app.api import workspaces as workspaces_api

from .conftest import login


def test_workspace_creation_renders_configs(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    client.post("/api/users", json={"username": "alice", "password": "alice-password", "role": "user", "is_active": True})
    client.post("/api/auth/logout")
    login(client, "alice", "alice-password")

    create_response = client.post("/api/workspaces", json={"name": "Alice Primary"})
    assert create_response.status_code == 201, create_response.text
    workspace = create_response.json()
    assert workspace["workspace_type"] == "base"

    second_response = client.post("/api/workspaces", json={"name": "Alice Secondary"})
    assert second_response.status_code == 201, second_response.text

    detail_response = client.get(f"/api/workspaces/{workspace['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()

    local_root = Path(app_env["workspaces_local"])
    runtime_root = Path(app_env["runtime_root"])
    config_path = local_root / "2" / "alice-primary" / ".nanobot" / "config.json"
    gateway_path = local_root / "2" / "alice-primary" / ".nanobot" / "gateway.yaml"
    runtime_gateway_path = runtime_root / "nanobot" / str(workspace["id"]) / "gateway.yaml"
    assert config_path.exists()
    assert gateway_path.exists()
    assert runtime_gateway_path.exists()

    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert config_payload["workspace"]["slug"] == "alice-primary"
    assert "feishu" in config_payload["channels"]
    assert detail["runtime_status"]["listen_port"] == 18080

    second_detail = client.get(f"/api/workspaces/{second_response.json()['id']}").json()
    assert second_detail["runtime_status"]["listen_port"] == 18081

    workspace_types_response = client.get("/api/workspace-types")
    assert workspace_types_response.status_code == 200
    assert {item["key"] for item in workspace_types_response.json()} == {"base", "openclaw"}


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


def test_workspace_creation_invalid_runtime_template_cleans_up_directory(client: TestClient, app_env):
    settings = app.config.get_settings()
    original_template = settings.nanobot_unit_template
    settings.nanobot_unit_template = "claw-nanobot@{workspace_id}.service.{bad}"

    try:
        login(client, "admin", "admin-password")
        response = client.post("/api/workspaces", json={"name": "Broken Runtime"})
        assert response.status_code == 400
        assert "invalid NANOBOT_UNIT_TEMPLATE" in response.json()["detail"]

        local_root = Path(app_env["workspaces_local"])
        assert not (local_root / "1" / "broken-runtime").exists()
    finally:
        settings.nanobot_unit_template = original_template


def test_workspace_creation_render_failure_cleans_up_database_and_directory(client: TestClient, app_env, monkeypatch: pytest.MonkeyPatch):
    original_render = workspaces_api.render_workspace_artifacts

    def fail_render(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(workspaces_api, "render_workspace_artifacts", fail_render)

    login(client, "admin", "admin-password")
    response = client.post("/api/workspaces", json={"name": "Transient Failure"})
    assert response.status_code == 500
    assert "cleaned up" in response.json()["detail"]

    list_response = client.get("/api/workspaces")
    assert list_response.status_code == 200
    assert all(item["slug"] != "transient-failure" for item in list_response.json())

    local_root = Path(app_env["workspaces_local"])
    assert not (local_root / "1" / "transient-failure").exists()

    monkeypatch.setattr(workspaces_api, "render_workspace_artifacts", original_render)
    retry_response = client.post("/api/workspaces", json={"name": "Transient Failure"})
    assert retry_response.status_code == 201, retry_response.text
