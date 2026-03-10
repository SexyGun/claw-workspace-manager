from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.constants import MASKED_VALUE

from .conftest import login


def test_openclaw_workspace_creation_and_aggregate_rendering(client: TestClient, app_env):
    login(client, "admin", "admin-password")

    create_response = client.post("/api/workspaces", json={"name": "Claw Lab", "workspace_type": "openclaw"})
    assert create_response.status_code == 201, create_response.text
    workspace = create_response.json()
    assert workspace["activation_state"] == "inactive"

    channel_response = client.put(
        f"/api/workspaces/{workspace['id']}/openclaw-channel-config",
        json={
            "values": {
                "enabled": True,
                "account_id": "feishu-claw-lab",
                "app_id": "app-claw-lab",
                "app_secret": "secret-claw-lab",
            }
        },
    )
    assert channel_response.status_code == 200, channel_response.text

    inactive_detail = client.get(f"/api/workspaces/{workspace['id']}")
    assert inactive_detail.status_code == 200
    assert inactive_detail.json()["workspace"]["activation_state"] == "inactive"

    start_response = client.post(f"/api/workspaces/{workspace['id']}/runtime/start")
    assert start_response.status_code == 200
    assert start_response.json()["state"] == "configured"

    detail_response = client.get(f"/api/workspaces/{workspace['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["openclaw_config"] is not None
    assert detail["openclaw_channel_config"] is not None
    assert detail["workspace"]["activation_state"] == "active"
    assert detail["openclaw_route"]["enabled"] is True
    assert detail["shared_runtime_status"]["scope"] == "shared"
    assert detail["overview"]["dashboard_state"] == "stopped"
    assert detail["health"]["route_state"] == "connected"

    list_response = client.get("/api/workspaces")
    assert list_response.status_code == 200
    listed = {item["id"]: item for item in list_response.json()}
    assert listed[workspace["id"]]["activation_state"] == "active"
    assert listed[workspace["id"]]["dashboard_state"] == "stopped"

    admin_list_response = client.get("/api/workspaces/admin/all")
    assert admin_list_response.status_code == 200
    admin_listed = {item["id"]: item for item in admin_list_response.json()}
    assert admin_listed[workspace["id"]]["activation_state"] == "active"

    local_root = Path(app_env["workspaces_local"])
    runtime_root = Path(app_env["runtime_root"])
    openclaw_json = local_root / "1" / "claw-lab" / ".openclaw" / "openclaw.json"
    channel_json = local_root / "1" / "claw-lab" / ".openclaw" / "channel.json"
    workspace_dir = local_root / "1" / "claw-lab" / ".openclaw" / "workspace"
    aggregate_json = runtime_root / "openclaw" / "openclaw.json"

    assert openclaw_json.exists()
    assert channel_json.exists()
    assert workspace_dir.exists()
    assert (workspace_dir / "AGENTS.md").exists()
    assert aggregate_json.exists()

    payload = json.loads(openclaw_json.read_text(encoding="utf-8"))
    assert payload["gateway"]["mode"] == "local"
    assert "model" not in payload
    assert "sandbox" not in payload
    assert payload["agents"]["defaults"]["workspace"] == str(workspace_dir)
    assert payload["agents"]["defaults"]["model"]["primary"] == "claude-3-7-sonnet"
    assert payload["agents"]["defaults"]["sandbox"]["mode"] == "non-main"
    assert payload["session"]["dmScope"] == "main"

    aggregate = json.loads(aggregate_json.read_text(encoding="utf-8"))
    assert aggregate["gateway"]["mode"] == "local"
    assert aggregate["agents"]["list"][0]["workspace"] == str(workspace_dir)
    assert aggregate["channels"]["feishu"]["accounts"][0]["id"] == "feishu-claw-lab"
    assert aggregate["bindings"][0]["agentId"] == f"workspace-{workspace['id']}"
    assert aggregate["bindings"][0]["match"]["accountId"] == "feishu-claw-lab"
    assert "session" not in aggregate["agents"]["list"][0]

def test_openclaw_config_supports_explicit_provider_fields_and_masks_secret(client: TestClient, app_env):
    login(client, "admin", "admin-password")

    workspace = client.post("/api/workspaces", json={"name": "Provider Lab", "workspace_type": "openclaw"}).json()
    workspace_id = workspace["id"]

    save_response = client.put(
        f"/api/workspaces/{workspace_id}/openclaw-config",
        json={
            "structured_values": {
                "primary_model": "moonshot/kimi-k2.5",
                "provider_id": "moonshot",
                "provider_base_url": "https://api.moonshot.ai/v1",
                "provider_api_key": "${MOONSHOT_API_KEY}",
                "provider_auth": "api-key",
                "provider_api": "openai-completions",
                "provider_models_json5": """
                [
                  {
                    id: "kimi-k2.5",
                    name: "Kimi K2.5",
                    reasoning: true,
                    input: ["text", "image"],
                    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
                    contextWindow: 128000,
                    maxTokens: 8192
                  }
                ]
                """,
            }
        },
    )
    assert save_response.status_code == 200, save_response.text

    detail_response = client.get(f"/api/workspaces/{workspace_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["openclaw_config"]["values"]["provider_id"] == "moonshot"
    assert detail["openclaw_config"]["values"]["provider_api_key"] == MASKED_VALUE
    assert MASKED_VALUE in detail["openclaw_config"]["raw_json5"]

    rendered_path = Path(app_env["workspaces_local"]) / "1" / "provider-lab" / ".openclaw" / "openclaw.json"
    rendered_workspace_path = Path(app_env["workspaces_local"]) / "1" / "provider-lab" / ".openclaw" / "workspace"
    payload = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert payload["gateway"]["mode"] == "local"
    assert "model" not in payload
    assert "sandbox" not in payload
    assert payload["agents"]["defaults"]["workspace"] == str(rendered_workspace_path)
    provider = payload["models"]["providers"]["moonshot"]
    assert provider["baseUrl"] == "https://api.moonshot.ai/v1"
    assert provider["apiKey"] == "${MOONSHOT_API_KEY}"
    assert provider["models"][0]["id"] == "kimi-k2.5"

    aggregate_path = Path(app_env["runtime_root"]) / "openclaw" / "openclaw.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    assert aggregate["models"]["providers"]["moonshot"]["apiKey"] == "${MOONSHOT_API_KEY}"


def test_openclaw_workspace_activation_follows_route_not_shared_service(client: TestClient):
    login(client, "admin", "admin-password")

    workspace = client.post("/api/workspaces", json={"name": "Route Only", "workspace_type": "openclaw"}).json()
    workspace_id = workspace["id"]

    initial_detail = client.get(f"/api/workspaces/{workspace_id}")
    assert initial_detail.status_code == 200
    assert initial_detail.json()["workspace"]["activation_state"] == "inactive"
    assert initial_detail.json()["shared_runtime_status"]["state"] == "stopped"

    enable_response = client.put(
        f"/api/workspaces/{workspace_id}/openclaw-channel-config",
        json={
            "values": {
                "enabled": True,
                "account_id": "route-only",
                "app_id": "route-only-app",
                "app_secret": "route-only-secret",
            }
        },
    )
    assert enable_response.status_code == 200, enable_response.text

    still_inactive = client.get(f"/api/workspaces/{workspace_id}")
    assert still_inactive.status_code == 200
    assert still_inactive.json()["workspace"]["activation_state"] == "inactive"

    route_start = client.post(f"/api/workspaces/{workspace_id}/runtime/start")
    assert route_start.status_code == 200

    active_detail = client.get(f"/api/workspaces/{workspace_id}")
    assert active_detail.status_code == 200
    assert active_detail.json()["workspace"]["activation_state"] == "active"
    assert active_detail.json()["shared_runtime_status"]["state"] == "stopped"

    start_response = client.post("/api/runtime/openclaw/service/start")
    assert start_response.status_code == 200
    assert start_response.json()["state"] == "running"

    running_detail = client.get(f"/api/workspaces/{workspace_id}")
    assert running_detail.status_code == 200
    assert running_detail.json()["workspace"]["activation_state"] == "active"
    assert running_detail.json()["shared_runtime_status"]["state"] == "running"

    stop_response = client.post("/api/runtime/openclaw/service/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["state"] == "stopped"

    stopped_detail = client.get(f"/api/workspaces/{workspace_id}")
    assert stopped_detail.status_code == 200
    assert stopped_detail.json()["workspace"]["activation_state"] == "active"
    assert stopped_detail.json()["shared_runtime_status"]["state"] == "stopped"


def test_openclaw_runtime_restart_endpoint_reloads_route_without_name_error(client: TestClient):
    login(client, "admin", "admin-password")

    workspace = client.post("/api/workspaces", json={"name": "Restart Route", "workspace_type": "openclaw"}).json()
    workspace_id = workspace["id"]

    enable_response = client.put(
        f"/api/workspaces/{workspace_id}/openclaw-channel-config",
        json={
            "values": {
                "enabled": True,
                "account_id": "restart-route",
                "app_id": "restart-app",
                "app_secret": "restart-secret",
            }
        },
    )
    assert enable_response.status_code == 200, enable_response.text

    start_response = client.post(f"/api/workspaces/{workspace_id}/runtime/start")
    assert start_response.status_code == 200
    assert start_response.json()["state"] == "configured"

    restart_response = client.post(f"/api/workspaces/{workspace_id}/runtime/restart")
    assert restart_response.status_code == 200, restart_response.text
    assert restart_response.json()["state"] == "configured"

    detail_response = client.get(f"/api/workspaces/{workspace_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["workspace"]["activation_state"] == "active"


def test_openclaw_setup_config_and_diagnostics(client: TestClient, app_env):
    login(client, "admin", "admin-password")

    workspace = client.post("/api/workspaces", json={"name": "Guided Claw", "workspace_type": "openclaw"}).json()
    workspace_id = workspace["id"]

    setup_response = client.put(
        f"/api/workspaces/{workspace_id}/setup-config",
        json={
            "openclaw": {
                "primary_model": "moonshot/kimi-k2.5",
                "provider_id": "moonshot",
                "provider_base_url": "https://api.moonshot.ai/v1",
                "provider_api_key": "${MOONSHOT_API_KEY}",
                "provider_api": "openai-completions",
                "provider_auth": "api-key",
            },
            "openclaw_channel": {
                "enabled": True,
                "account_id": "guided-claw",
                "app_id": "guided-app",
                "app_secret": "guided-secret",
            },
            "start_after_save": True,
        },
    )
    assert setup_response.status_code == 200, setup_response.text
    summary = setup_response.json()
    assert summary["workspace"]["activation_state"] == "active"
    assert summary["setup_progress"]["completion_percent"] == 100
    assert summary["overview"]["channel_summary"] == "Feishu · guided-claw"
    assert summary["health"]["service_state"] == "stopped"

    checks_response = client.post(f"/api/workspaces/{workspace_id}/diagnostics/checks")
    assert checks_response.status_code == 200
    checks = {item["code"]: item for item in checks_response.json()["checks"]}
    assert checks["route_enabled"]["status"] == "ok"
    assert checks["shared_service"]["status"] == "warn"

    logs_response = client.get(f"/api/workspaces/{workspace_id}/diagnostics/logs")
    assert logs_response.status_code == 200
    assert logs_response.json()["entries"]

    aggregate_path = Path(app_env["runtime_root"]) / "openclaw" / "openclaw.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    assert aggregate["bindings"][0]["agentId"] == f"workspace-{workspace_id}"
    assert aggregate["bindings"][0]["match"]["accountId"] == "guided-claw"


def test_openclaw_shared_service_requires_admin(client: TestClient):
    login(client, "admin", "admin-password")
    client.post("/api/users", json={"username": "alice", "password": "alice-password", "role": "user", "is_active": True})

    admin_start = client.post("/api/runtime/openclaw/service/start")
    assert admin_start.status_code == 200
    assert admin_start.json()["state"] == "running"

    client.post("/api/auth/logout")
    login(client, "alice", "alice-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Claw Ops", "workspace_type": "openclaw"}).json()["id"]

    detail_response = client.get(f"/api/workspaces/{workspace_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["shared_runtime_status"]["state"] == "running"

    forbidden = client.post("/api/runtime/openclaw/service/restart")
    assert forbidden.status_code == 403
