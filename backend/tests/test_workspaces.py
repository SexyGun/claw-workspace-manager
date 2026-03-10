from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

import app.config
from app import models
from app.api import workspaces as workspaces_api
from app.db import SessionLocal

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
    runtime_config_path = runtime_root / "nanobot" / str(workspace["id"]) / "config.json"
    runtime_env_path = runtime_root / "nanobot" / str(workspace["id"]) / "runtime.env"
    assert config_path.exists()
    assert runtime_config_path.exists()
    assert runtime_env_path.exists()
    assert not (local_root / "2" / "alice-primary" / ".nanobot" / "gateway.yaml").exists()

    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert config_payload["agents"]["defaults"]["workspace"] == str(Path(workspace["host_path"]) / "workspace")
    assert config_payload["gateway"]["port"] == 18080
    assert config_payload["providers"]["custom"]["api_base"] == "http://localhost:8000/v1"
    assert config_payload["tools"]["restrict_to_workspace"] is True
    assert "feishu" in config_payload["channels"]
    assert workspace["activation_state"] == "inactive"
    assert detail["runtime_status"]["listen_port"] == 18080
    assert detail["runtime_status"]["config_path"] == str(runtime_config_path)
    assert detail["runtime_status"]["workspace_path"] == str(Path(workspace["host_path"]) / "workspace")

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


def test_gateway_config_endpoints_are_gone(client: TestClient):
    login(client, "admin", "admin-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Native Runtime"}).json()["id"]

    get_response = client.get(f"/api/workspaces/{workspace_id}/gateway-config")
    assert get_response.status_code == 410

    put_response = client.put(f"/api/workspaces/{workspace_id}/gateway-config", json={"values": {}})
    assert put_response.status_code == 410


def test_saving_nanobot_config_marks_running_workspace_for_restart(client: TestClient):
    login(client, "admin", "admin-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Restart Me"}).json()["id"]

    start_response = client.post(f"/api/workspaces/{workspace_id}/runtime/start")
    assert start_response.status_code == 200
    assert start_response.json()["needs_restart"] is False

    save_response = client.put(
        f"/api/workspaces/{workspace_id}/nanobot-config",
        json={"values": {"feishu": {"enabled": True, "app_id": "app-1", "app_secret": "secret-1"}}},
    )
    assert save_response.status_code == 200, save_response.text

    detail_response = client.get(f"/api/workspaces/{workspace_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["runtime_status"]["needs_restart"] is True

    restart_response = client.post(f"/api/workspaces/{workspace_id}/runtime/restart")
    assert restart_response.status_code == 200
    assert restart_response.json()["needs_restart"] is False


def test_legacy_qq_config_shows_warning_and_requires_manual_reentry(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    workspace = client.post("/api/workspaces", json={"name": "Legacy QQ"}).json()
    workspace_id = workspace["id"]

    db = SessionLocal()
    try:
        record = db.get(models.WorkspaceConfig, workspace_id)
        assert record is not None
        record.channel_config_json = {
            "feishu": {"enabled": False, "app_id": "", "app_secret": "", "webhook": ""},
            "dingtalk": {"enabled": False, "app_key": "", "app_secret": "", "robot_code": "", "webhook": ""},
            "qq": {"enabled": True, "bot_uin": "123456", "token": "legacy-token", "websocket_url": "ws://legacy"},
        }
        db.add(record)
        db.commit()
    finally:
        db.close()

    detail_response = client.get(f"/api/workspaces/{workspace_id}")
    assert detail_response.status_code == 200
    nanobot_config = detail_response.json()["nanobot_config"]
    assert nanobot_config["warnings"] == [
        "QQ legacy config could not be migrated automatically; re-enter App ID and Secret."
    ]
    assert nanobot_config["values"]["qq"]["app_id"] == ""
    assert nanobot_config["values"]["qq"]["secret"] == ""

    save_response = client.put(
        f"/api/workspaces/{workspace_id}/nanobot-config",
        json={"values": {"feishu": {"enabled": False, "app_id": "", "app_secret": ""}}},
    )
    assert save_response.status_code == 200, save_response.text

    config_path = Path(app_env["workspaces_local"]) / "1" / "legacy-qq" / ".nanobot" / "config.json"
    rendered = json.loads(config_path.read_text(encoding="utf-8"))
    assert "token" not in rendered["channels"]["qq"]
    assert "bot_uin" not in rendered["channels"]["qq"]
    assert rendered["channels"]["qq"]["app_id"] == ""
