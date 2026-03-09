from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import login


def test_openclaw_workspace_creation_and_aggregate_rendering(client: TestClient, app_env):
    login(client, "admin", "admin-password")

    create_response = client.post("/api/workspaces", json={"name": "Claw Lab", "workspace_type": "openclaw"})
    assert create_response.status_code == 201, create_response.text
    workspace = create_response.json()

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

    detail_response = client.get(f"/api/workspaces/{workspace['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["openclaw_config"] is not None
    assert detail["openclaw_channel_config"] is not None
    assert detail["openclaw_route"]["enabled"] is True
    assert detail["shared_runtime_status"]["scope"] == "shared"

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
    assert payload["model"]["primary"] == "claude-3-7-sonnet"

    aggregate = json.loads(aggregate_json.read_text(encoding="utf-8"))
    assert aggregate["agents"]["list"][0]["workspace"] == str(workspace_dir)
    assert aggregate["channels"]["feishu"]["accounts"][0]["id"] == "feishu-claw-lab"
    assert aggregate["bindings"][0]["agentId"] == f"workspace-{workspace['id']}"


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
