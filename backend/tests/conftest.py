from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app_env(tmp_path_factory) -> Iterator[dict[str, Path]]:
    root = tmp_path_factory.mktemp("claw-workspace-manager")
    sqlite_dir = root / "sqlite"
    workspaces_local = root / "workspaces-local"
    workspaces_host = root / "workspaces-host"
    runtime_root = root / "runtime"
    templates_root = root / "templates"
    base_templates = templates_root / "base-workspace"
    openclaw_templates = templates_root / "openclaw-workspace"
    fake_systemctl_state = root / "fake-systemctl-state.json"
    fake_systemctl = root / "fake-systemctl"

    base_templates.mkdir(parents=True, exist_ok=True)
    (base_templates / "README.md").write_text("base template", encoding="utf-8")

    (openclaw_templates / ".openclaw" / "workspace").mkdir(parents=True, exist_ok=True)
    (openclaw_templates / ".openclaw" / "openclaw.json").write_text(
        """{
  model: { primary: "claude-3-7-sonnet", fallbacks: ["gpt-4.1-mini"] },
  sandbox: { mode: "workspace-write" },
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

    fake_systemctl.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


STATE_FILE = Path(os.environ["FAKE_SYSTEMCTL_STATE"])


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"units": {}, "next_pid": 1000}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def unit_entry(state: dict, unit: str) -> dict:
    return state["units"].setdefault(
        unit,
        {"active_state": "inactive", "main_pid": 0, "active_usec": 0, "inactive_usec": 0},
    )


def now_usec() -> int:
    return int(time.time() * 1_000_000)


def main(argv: list[str]) -> int:
    if not argv:
        return 1
    cmd = argv[0]
    state = load_state()

    if cmd in {"start", "stop", "restart", "reload"}:
        unit = argv[1]
        entry = unit_entry(state, unit)
        if cmd == "stop":
            entry["active_state"] = "inactive"
            entry["main_pid"] = 0
            entry["inactive_usec"] = now_usec()
        elif cmd == "reload":
            if entry["active_state"] != "active":
                sys.stderr.write("Unit is not running\\n")
                return 1
        else:
            state["next_pid"] += 1
            entry["active_state"] = "active"
            entry["main_pid"] = state["next_pid"]
            entry["active_usec"] = now_usec()
            entry["inactive_usec"] = 0
        save_state(state)
        return 0

    if cmd == "show":
        unit = argv[1]
        entry = unit_entry(state, unit)
        save_state(state)
        sys.stdout.write(
            "\\n".join(
                [
                    f"ActiveState={entry['active_state']}",
                    f"MainPID={entry['main_pid']}",
                    f"ActiveEnterTimestampUSec={entry['active_usec']}",
                    f"InactiveEnterTimestampUSec={entry['inactive_usec']}",
                ]
            )
            + "\\n"
        )
        return 0

    sys.stderr.write(f"Unsupported command: {cmd}\\n")
    return 1


raise SystemExit(main(sys.argv[1:]))
""",
        encoding="utf-8",
    )
    fake_systemctl.chmod(0o755)

    sqlite_dir.mkdir(parents=True, exist_ok=True)
    workspaces_local.mkdir(parents=True, exist_ok=True)
    workspaces_host.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)

    env = {
        "APP_ENV": "test",
        "SESSION_SECRET": "test-secret",
        "SQLITE_PATH": str(sqlite_dir / "app.db"),
        "WORKSPACE_ROOT": str(workspaces_local),
        "HOST_WORKSPACE_ROOT": str(workspaces_host),
        "RUNTIME_STATE_ROOT": str(runtime_root),
        "WORKSPACE_TEMPLATE_ROOT": str(base_templates),
        "OPENCLAW_WORKSPACE_TEMPLATE_ROOT": str(openclaw_templates),
        "SYSTEMCTL_COMMAND": str(fake_systemctl),
        "SYSTEMCTL_USE_SUDO": "false",
        "FAKE_SYSTEMCTL_STATE": str(fake_systemctl_state),
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
        "runtime_root": runtime_root,
        "base_templates": base_templates,
        "openclaw_templates": openclaw_templates,
        "fake_systemctl_state": fake_systemctl_state,
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
        yield test_client


def login(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
