from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class _BaseFakeRuntimeManager:
    instance_attr = ""
    id_prefix = "fake"

    def sync_managed_containers(self, db):
        return None

    def _instance(self, workspace):
        return getattr(workspace, self.instance_attr)

    def status(self, db, workspace):
        instance = self._instance(workspace)
        return type(
            "RuntimeState",
            (),
            {
                "state": instance.state,
                "container_name": instance.container_name,
                "container_id": instance.last_container_id,
                "last_error": instance.last_error,
                "started_at": instance.started_at,
                "stopped_at": instance.stopped_at,
            },
        )()

    def start(self, db, workspace):
        instance = self._instance(workspace)
        instance.state = "running"
        instance.last_container_id = f"{self.id_prefix}-{workspace.id}"
        instance.last_error = None
        instance.started_at = datetime.now(timezone.utc)
        instance.stopped_at = None
        db.add(instance)
        db.commit()
        return self.status(db, workspace)

    def stop(self, db, workspace):
        instance = self._instance(workspace)
        instance.state = "stopped"
        instance.stopped_at = datetime.now(timezone.utc)
        db.add(instance)
        db.commit()
        return self.status(db, workspace)

    def restart(self, db, workspace):
        return self.start(db, workspace)


class FakeGatewayManager(_BaseFakeRuntimeManager):
    instance_attr = "gateway_instance"
    id_prefix = "fake-gateway"


class FakeOpenClawManager(_BaseFakeRuntimeManager):
    instance_attr = "openclaw_instance"
    id_prefix = "fake-openclaw"


@pytest.fixture(scope="session")
def app_env(tmp_path_factory) -> Iterator[dict[str, Path]]:
    root = tmp_path_factory.mktemp("claw-workspace-manager")
    sqlite_dir = root / "sqlite"
    workspaces_local = root / "workspaces-local"
    workspaces_host = root / "workspaces-host"
    templates_root = root / "templates"
    base_templates = templates_root / "base-workspace"
    openclaw_templates = templates_root / "openclaw-workspace"

    base_templates.mkdir(parents=True, exist_ok=True)
    (base_templates / "README.md").write_text("base template", encoding="utf-8")

    (openclaw_templates / ".openclaw" / "workspace").mkdir(parents=True, exist_ok=True)
    (openclaw_templates / ".openclaw" / "openclaw.json").write_text(
        """{
  gateway: { port: 7444, },
  agents: {
    defaults: {
      model: { primary: "claude-3-7-sonnet", fallbacks: ["gpt-4.1-mini"] },
      sandbox: { mode: "workspace-write" }
    }
  },
  session: { dmScope: "workspace" },
  hooks: { enabled: false, path: ".openclaw/hooks.js", token: "" },
  cron: { enabled: false, maxConcurrentRuns: 2 }
}
""",
        encoding="utf-8",
    )
    for file_name in ["AGENTS.md", "SOUL.md", "USER.md", "IDENTITY.md", "TOOLS.md"]:
        (openclaw_templates / ".openclaw" / "workspace" / file_name).write_text(
            f"# {file_name}\n",
            encoding="utf-8",
        )

    sqlite_dir.mkdir(parents=True, exist_ok=True)
    workspaces_local.mkdir(parents=True, exist_ok=True)
    workspaces_host.mkdir(parents=True, exist_ok=True)

    env = {
        "APP_ENV": "test",
        "SESSION_SECRET": "test-secret",
        "SQLITE_PATH": str(sqlite_dir / "app.db"),
        "WORKSPACE_ROOT": str(workspaces_local),
        "HOST_WORKSPACE_ROOT": str(workspaces_host),
        "WORKSPACE_TEMPLATE_ROOT": str(base_templates),
        "OPENCLAW_WORKSPACE_TEMPLATE_ROOT": str(openclaw_templates),
        "OPENCLAW_IMAGE": "ghcr.io/example/openclaw:test",
        "BOOTSTRAP_ADMIN_USERNAME": "admin",
        "BOOTSTRAP_ADMIN_PASSWORD": "admin-password",
    }

    previous = {key: os.environ.get(key) for key in env}
    os.environ.update(env)
    yield {
        "root": root,
        "sqlite_dir": sqlite_dir,
        "workspaces_local": workspaces_local,
        "workspaces_host": workspaces_host,
        "base_templates": base_templates,
        "openclaw_templates": openclaw_templates,
    }
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture()
def client(app_env) -> Iterator[TestClient]:
    import app.config

    app.config.get_settings.cache_clear()
    from app.db import Base, engine
    from app.main import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        test_client.app.state.gateway_manager = FakeGatewayManager()
        test_client.app.state.openclaw_manager = FakeOpenClawManager()
        yield test_client


def login(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
