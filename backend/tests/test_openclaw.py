from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import login


def test_openclaw_workspace_creation_and_rendering(client: TestClient, app_env):
    login(client, "admin", "admin-password")

    create_response = client.post("/api/workspaces", json={"name": "Claw Lab", "workspace_type": "openclaw"})
    assert create_response.status_code == 201, create_response.text
    workspace = create_response.json()
    assert workspace["workspace_type"] == "openclaw"

    detail_response = client.get(f"/api/workspaces/{workspace['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["openclaw_config"] is not None
    assert detail["gateway_config"] is None

    local_root = Path(app_env["workspaces_local"])
    openclaw_json = local_root / "1" / "claw-lab" / ".openclaw" / "openclaw.json"
    workspace_dir = local_root / "1" / "claw-lab" / ".openclaw" / "workspace"
    assert openclaw_json.exists()
    assert workspace_dir.exists()
    assert (workspace_dir / "AGENTS.md").exists()

    payload = json.loads(openclaw_json.read_text(encoding="utf-8"))
    assert payload["agents"]["defaults"]["workspace"] == "~/.openclaw/workspace"


def test_openclaw_config_preserves_unknown_raw_fields_and_runtime(client: TestClient):
    login(client, "admin", "admin-password")
    workspace_id = client.post("/api/workspaces", json={"name": "Claw Ops", "workspace_type": "openclaw"}).json()["id"]

    update_response = client.put(
        f"/api/workspaces/{workspace_id}/openclaw-config",
        json={
            "structured_values": {
                "gateway_port": 9555,
                "fallback_models": "gpt-4.1-mini, claude-3-haiku",
                "cron_enabled": True,
            },
            "raw_json5": """
            {
              gateway: { port: 8111, },
              customFeature: { enabled: true },
              hooks: { enabled: true, path: ".openclaw/custom-hooks.js", token: "hook-secret" }
            }
            """,
        },
    )
    assert update_response.status_code == 200, update_response.text
    body = update_response.json()
    assert body["values"]["gateway_port"] == 9555
    assert "customFeature" in body["raw_json5"]

    start_response = client.post(f"/api/workspaces/{workspace_id}/openclaw/start")
    assert start_response.status_code == 200
    assert start_response.json()["state"] == "running"

    mismatch_response = client.post(f"/api/workspaces/{workspace_id}/gateway/start")
    assert mismatch_response.status_code == 400
