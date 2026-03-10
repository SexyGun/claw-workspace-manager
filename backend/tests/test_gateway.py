from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import login


def test_workspace_runtime_lifecycle(client: TestClient, app_env):
    login(client, "admin", "admin-password")
    workspace = client.post("/api/workspaces", json={"name": "Gateway Space"}).json()
    workspace_id = workspace["id"]
    runtime_config_path = Path(app_env["runtime_root"]) / "nanobot" / str(workspace_id) / "config.json"
    runtime_config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "feishu": {
                        "enabled": True,
                        "app_id": "legacy-app",
                        "app_secret": "legacy-secret",
                        "allow_from": [],
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    start_response = client.post(f"/api/workspaces/{workspace_id}/runtime/start")
    assert start_response.status_code == 200
    assert start_response.json()["state"] == "running"
    assert start_response.json()["unit_name"] == f"claw-nanobot@{workspace_id}.service"
    assert start_response.json()["config_path"].endswith(f"/nanobot/{workspace_id}/config.json")
    assert start_response.json()["workspace_path"] == f"{workspace['host_path']}/workspace"
    runtime_payload = json.loads(runtime_config_path.read_text(encoding="utf-8"))
    assert runtime_payload["channels"]["feishu"]["allowFrom"] == ["*"]

    status_response = client.get(f"/api/workspaces/{workspace_id}/runtime")
    assert status_response.status_code == 200
    assert status_response.json()["state"] == "running"
    assert status_response.json()["listen_port"] == 18080

    list_response = client.get("/api/workspaces")
    assert list_response.status_code == 200
    assert list_response.json()[0]["activation_state"] == "active"
    assert list_response.json()[0]["listen_port"] == 18080

    stop_response = client.post(f"/api/workspaces/{workspace_id}/runtime/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["state"] == "stopped"
