from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class FakeGatewayManager:
    def sync_managed_containers(self, db):
        return None

    def status(self, db, workspace):
        instance = workspace.gateway_instance
        return type(
            "GatewayState",
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
        instance = workspace.gateway_instance
        instance.state = "running"
        instance.last_container_id = f"fake-{workspace.id}"
        instance.last_error = None
        instance.started_at = datetime.now(timezone.utc)
        instance.stopped_at = None
        db.add(instance)
        db.commit()
        return self.status(db, workspace)

    def stop(self, db, workspace):
        instance = workspace.gateway_instance
        instance.state = "stopped"
        instance.stopped_at = datetime.now(timezone.utc)
        db.add(instance)
        db.commit()
        return self.status(db, workspace)

    def restart(self, db, workspace):
        return self.start(db, workspace)


@pytest.fixture(scope="session")
def app_env(tmp_path_factory) -> Iterator[dict[str, Path]]:
    root = tmp_path_factory.mktemp("claw-workspace-manager")
    sqlite_dir = root / "sqlite"
    workspaces_local = root / "workspaces-local"
    workspaces_host = root / "workspaces-host"
    templates = root / "templates" / "base-workspace"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "README.md").write_text("template", encoding="utf-8")
    sqlite_dir.mkdir(parents=True, exist_ok=True)
    workspaces_local.mkdir(parents=True, exist_ok=True)
    workspaces_host.mkdir(parents=True, exist_ok=True)

    env = {
        "APP_ENV": "test",
        "SESSION_SECRET": "test-secret",
        "SQLITE_PATH": str(sqlite_dir / "app.db"),
        "WORKSPACE_ROOT": str(workspaces_local),
        "HOST_WORKSPACE_ROOT": str(workspaces_host),
        "WORKSPACE_TEMPLATE_ROOT": str(templates),
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
        "templates": templates,
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
        yield test_client


def login(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
