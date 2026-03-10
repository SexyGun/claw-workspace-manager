from __future__ import annotations

import json
import shutil
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
    assert config_payload["channels"]["feishu"]["allowFrom"] == ["*"]
    assert workspace["activation_state"] == "inactive"
    assert workspace["listen_port"] == 18080
    assert detail["nanobot_agent_config"]["values"]["model"] == "anthropic/claude-sonnet-4-5"
    assert detail["nanobot_agent_config"]["values"]["provider"] == "auto"
    assert detail["nanobot_provider_config"]["values"]["custom"]["api_base"] == "http://localhost:8000/v1"
    assert detail["runtime_status"]["listen_port"] == 18080
    assert detail["runtime_status"]["config_path"] == str(runtime_config_path)
    assert detail["runtime_status"]["workspace_path"] == str(Path(workspace["host_path"]) / "workspace")

    second_detail = client.get(f"/api/workspaces/{second_response.json()['id']}").json()
    assert second_detail["runtime_status"]["listen_port"] == 18081

    list_response = client.get("/api/workspaces")
    assert list_response.status_code == 200
    listed = {item["id"]: item for item in list_response.json()}
    assert listed[workspace["id"]]["listen_port"] == 18080
    assert listed[second_response.json()["id"]]["listen_port"] == 18081
    assert listed[workspace["id"]]["dashboard_state"] == "needs_setup"
    assert listed[workspace["id"]]["channel_summary"] == "未配置"
    assert listed[workspace["id"]]["model_summary"] == "anthropic/claude-sonnet-4-5"
    assert listed[workspace["id"]]["completion_percent"] == 80

    assert detail["overview"]["dashboard_state"] == "needs_setup"
    assert detail["overview"]["entry_label"] == "网关端口"
    assert detail["health"]["service_state"] == "stopped"
    assert detail["health"]["config_state"] == "incomplete"
    assert "绑定渠道" in detail["recommended_actions"]
    assert detail["setup_progress"]["completion_percent"] == 80

    workspace_types_response = client.get("/api/workspace-types")
    assert workspace_types_response.status_code == 200
    assert {item["key"] for item in workspace_types_response.json()} == {"base", "openclaw"}


def test_workspace_host_paths_reconcile_when_root_changes(app_env, monkeypatch: pytest.MonkeyPatch):
    app.config.get_settings.cache_clear()
    from app.db import Base, SessionLocal, engine
    from app.main import app as app_instance

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app_instance) as initial_client:
        login(initial_client, "admin", "admin-password")
        workspace = initial_client.post("/api/workspaces", json={"name": "Moved Root"}).json()

    workspace_id = workspace["id"]
    relative_path = Path(str(workspace["owner_user_id"])) / workspace["slug"]
    old_local_workspace = Path(app_env["workspaces_local"]) / relative_path
    new_local_root = Path(app_env["root"]) / "workspaces-local-migrated"
    new_host_root = Path(app_env["root"]) / "workspaces-host-migrated"
    new_local_workspace = new_local_root / relative_path

    new_local_workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_local_workspace), str(new_local_workspace))

    monkeypatch.setenv("WORKSPACE_ROOT", str(new_local_root))
    monkeypatch.setenv("HOST_WORKSPACE_ROOT", str(new_host_root))
    app.config.get_settings.cache_clear()

    with TestClient(app_instance) as migrated_client:
        login(migrated_client, "admin", "admin-password")
        detail_response = migrated_client.get(f"/api/workspaces/{workspace_id}")
        assert detail_response.status_code == 200, detail_response.text
        detail = detail_response.json()
        expected_host_path = str(new_host_root / relative_path)
        assert detail["workspace"]["host_path"] == expected_host_path
        assert detail["runtime_status"]["workspace_path"] == f"{expected_host_path}/workspace"

    runtime_config_path = Path(app_env["runtime_root"]) / "nanobot" / str(workspace_id) / "config.json"
    runtime_payload = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    assert runtime_payload["agents"]["defaults"]["workspace"] == f"{expected_host_path}/workspace"

    db = SessionLocal()
    try:
        refreshed = db.get(models.Workspace, workspace_id)
        assert refreshed is not None
        assert refreshed.host_path == expected_host_path
    finally:
        db.close()


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


def test_workspace_setup_config_saves_all_sections_and_can_start(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    workspace = client.post("/api/workspaces", json={"name": "Setup Flow"}).json()
    workspace_id = workspace["id"]

    setup_response = client.put(
        f"/api/workspaces/{workspace_id}/setup-config",
        json={
            "nanobot": {
                "feishu": {
                    "enabled": True,
                    "app_id": "setup-app",
                    "app_secret": "setup-secret",
                }
            },
            "agent": {
                "model": "openrouter/openai/gpt-4.1-mini",
                "provider": "openrouter",
            },
            "provider": {
                "openrouter": {
                    "api_key": "sk-setup",
                    "api_base": "https://openrouter.ai/api/v1",
                }
            },
            "start_after_save": True,
        },
    )
    assert setup_response.status_code == 200, setup_response.text
    summary = setup_response.json()
    assert summary["workspace"]["activation_state"] == "active"
    assert summary["runtime_status"]["state"] == "running"
    assert summary["setup_progress"]["completion_percent"] == 100
    assert summary["overview"]["dashboard_state"] == "running"
    assert summary["health"]["config_state"] == "complete"

    runtime_config_path = Path(app_env["runtime_root"]) / "nanobot" / str(workspace_id) / "config.json"
    runtime_payload = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    assert runtime_payload["agents"]["defaults"]["model"] == "openrouter/openai/gpt-4.1-mini"
    assert runtime_payload["providers"]["openrouter"]["api_key"] == "sk-setup"
    assert runtime_payload["channels"]["feishu"]["app_id"] == "setup-app"


def test_workspace_diagnostics_and_delete_api(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    workspace = client.post("/api/workspaces", json={"name": "Diagnostics Space"}).json()
    workspace_id = workspace["id"]

    checks_response = client.post(f"/api/workspaces/{workspace_id}/diagnostics/checks")
    assert checks_response.status_code == 200
    checks = checks_response.json()["checks"]
    assert any(item["code"] == "channel_ready" for item in checks)

    logs_response = client.get(f"/api/workspaces/{workspace_id}/diagnostics/logs")
    assert logs_response.status_code == 200
    assert logs_response.json()["entries"]

    delete_response = client.delete(f"/api/workspaces/{workspace_id}")
    assert delete_response.status_code == 200

    list_response = client.get("/api/workspaces")
    assert list_response.status_code == 200
    assert all(item["id"] != workspace_id for item in list_response.json())
    local_root = Path(app_env["workspaces_local"])
    assert not (local_root / "1" / "diagnostics-space").exists()


def test_saving_provider_config_updates_runtime_config_and_masks_api_key(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    workspace = client.post("/api/workspaces", json={"name": "Providers"}).json()
    workspace_id = workspace["id"]

    save_response = client.put(
        f"/api/workspaces/{workspace_id}/provider-config",
        json={
            "values": {
                "openrouter": {
                    "api_key": "sk-or-test",
                    "api_base": "https://openrouter.ai/api/v1",
                    "extra_headers_json": '{"HTTP-Referer":"https://example.com","X-Title":"Claw"}',
                }
            }
        },
    )
    assert save_response.status_code == 200, save_response.text
    assert save_response.json()["values"]["openrouter"]["api_key"] == "__MASKED__"

    detail_response = client.get(f"/api/workspaces/{workspace_id}")
    assert detail_response.status_code == 200
    provider_values = detail_response.json()["nanobot_provider_config"]["values"]["openrouter"]
    assert provider_values["api_key"] == "__MASKED__"
    assert provider_values["api_base"] == "https://openrouter.ai/api/v1"
    assert provider_values["extra_headers_json"] == '{\n  "HTTP-Referer": "https://example.com",\n  "X-Title": "Claw"\n}'

    runtime_config_path = Path(app_env["runtime_root"]) / "nanobot" / str(workspace_id) / "config.json"
    runtime_payload = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    assert runtime_payload["providers"]["openrouter"]["api_key"] == "sk-or-test"
    assert runtime_payload["providers"]["openrouter"]["api_base"] == "https://openrouter.ai/api/v1"
    assert runtime_payload["providers"]["openrouter"]["extra_headers"]["X-Title"] == "Claw"


def test_saving_agent_config_updates_runtime_config(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    workspace = client.post("/api/workspaces", json={"name": "Agents"}).json()
    workspace_id = workspace["id"]

    save_response = client.put(
        f"/api/workspaces/{workspace_id}/agent-config",
        json={
            "values": {
                "model": "minimax/MiniMax-M2.5",
                "provider": "minimax",
            }
        },
    )
    assert save_response.status_code == 200, save_response.text
    assert save_response.json()["values"]["model"] == "minimax/MiniMax-M2.5"
    assert save_response.json()["values"]["provider"] == "minimax"

    detail_response = client.get(f"/api/workspaces/{workspace_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["nanobot_agent_config"]["values"]["model"] == "minimax/MiniMax-M2.5"
    assert detail_response.json()["nanobot_agent_config"]["values"]["provider"] == "minimax"

    runtime_config_path = Path(app_env["runtime_root"]) / "nanobot" / str(workspace_id) / "config.json"
    runtime_payload = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    assert runtime_payload["agents"]["defaults"]["model"] == "minimax/MiniMax-M2.5"
    assert runtime_payload["agents"]["defaults"]["provider"] == "minimax"


def test_agent_config_rejects_unsupported_provider(client: TestClient):
    login(client, "admin", "admin-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Bad Agent"}).json()["id"]

    response = client.put(
        f"/api/workspaces/{workspace_id}/agent-config",
        json={
            "values": {
                "model": "gpt-4.1",
                "provider": "not-real",
            }
        },
    )
    assert response.status_code == 400
    assert "agents.defaults.provider is not supported" in response.json()["detail"]


def test_provider_config_rejects_invalid_extra_headers_json(client: TestClient):
    login(client, "admin", "admin-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Bad Providers"}).json()["id"]

    response = client.put(
        f"/api/workspaces/{workspace_id}/provider-config",
        json={
            "values": {
                "custom": {
                    "extra_headers_json": '{"APP-Code": 1}',
                }
            }
        },
    )
    assert response.status_code == 400
    assert "extra_headers_json keys and values must be strings" in response.json()["detail"]


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


def test_legacy_manager_nanobot_config_is_sanitized_on_rerender(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    workspace = client.post("/api/workspaces", json={"name": "Legacy Manager Config"}).json()
    workspace_id = workspace["id"]

    local_config_path = Path(app_env["workspaces_local"]) / "1" / "legacy-manager-config" / ".nanobot" / "config.json"
    local_config_path.write_text(
        json.dumps(
            {
                "workspace": {"name": "legacy-manager-config", "slug": "legacy-manager-config"},
                "channels": {
                    "feishu": {"enabled": True, "app_id": "legacy-app", "app_secret": "legacy-secret"},
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    save_response = client.put(
        f"/api/workspaces/{workspace_id}/nanobot-config",
        json={"values": {"feishu": {"enabled": True, "app_id": "legacy-app", "app_secret": "legacy-secret"}}},
    )
    assert save_response.status_code == 200, save_response.text

    runtime_config_path = Path(app_env["runtime_root"]) / "nanobot" / str(workspace_id) / "config.json"
    runtime_payload = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    assert "workspace" not in runtime_payload
    assert runtime_payload["agents"]["defaults"]["workspace"] == str(Path(workspace["host_path"]) / "workspace")
