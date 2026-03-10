from __future__ import annotations

import grp
import os
import pwd
import shlex
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "deploy" / "install-native.sh"


def current_identity() -> tuple[str, str]:
    return pwd.getpwuid(os.getuid()).pw_name, grp.getgrgid(os.getgid()).gr_name


def run_install_shell(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    command = "\n".join(
        [
            "set -euo pipefail",
            f"source {shlex.quote(str(INSTALL_SCRIPT))}",
            script,
        ]
    )
    merged_env = os.environ.copy()
    merged_env.update(env)
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=REPO_ROOT,
        env=merged_env,
        capture_output=True,
        text=True,
    )


def base_env(tmp_path: Path) -> dict[str, str]:
    username, group = current_identity()
    fake_home = tmp_path / "service-home"
    fake_home.mkdir()
    return {
        "APP_USER": username,
        "APP_GROUP": group,
        "APP_HOME_OVERRIDE": str(fake_home),
        "INSTALL_ROOT": str(tmp_path / "install"),
        "APP_ROOT": str(tmp_path / "install" / "app"),
        "VENV_DIR": str(tmp_path / "install" / "venv"),
        "DATA_ROOT": str(tmp_path / "data"),
        "ENV_FILE": str(tmp_path / "etc" / "claw-workspace-manager.env"),
        "SYSTEMD_DIR": str(tmp_path / "systemd"),
        "SUDOERS_FILE": str(tmp_path / "sudoers" / "claw-workspace-manager"),
        "MANAGER_SERVICE": "claw-manager.service",
        "OPENCLAW_SHARED_UNIT": "claw-openclaw.service",
        "NANOBOT_UNIT_TEMPLATE": "claw-nanobot@{workspace_id}.service",
        "OPENCLAW_BIN": "/bin/true",
        "NANOBOT_BIN": "/bin/true",
        "SESSION_SECRET": "test-secret",
        "BOOTSTRAP_ADMIN_PASSWORD": "test-password",
        "SYSTEMCTL_BIN": "/bin/true",
        "SUDO_BIN": "/usr/bin/sudo",
    }


def test_install_native_uses_app_home_workspace_root_and_single_user_units(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    fake_home = Path(env["APP_HOME_OVERRIDE"])
    workspace_root = fake_home / "claw"
    runtime_root = Path(env["DATA_ROOT"]) / "runtime"
    env_file = Path(env["ENV_FILE"])
    systemd_dir = Path(env["SYSTEMD_DIR"])

    result = run_install_shell(
        """
normalize_nanobot_unit_template
ensure_single_user_runtime
initialize_paths
ensure_directories
write_env_file
write_openclaw_unit
write_nanobot_unit
""",
        env,
    )

    assert result.returncode == 0, result.stderr
    assert workspace_root.is_dir()

    env_text = env_file.read_text(encoding="utf-8")
    assert f"WORKSPACE_ROOT={workspace_root}" in env_text
    assert f"HOST_WORKSPACE_ROOT={workspace_root}" in env_text
    assert f"RUNTIME_USER={env['APP_USER']}" in env_text
    assert f"RUNTIME_GROUP={env['APP_GROUP']}" in env_text
    assert f"RUNTIME_HOME={fake_home}" in env_text

    openclaw_unit = (systemd_dir / "claw-openclaw.service").read_text(encoding="utf-8")
    assert f"User={env['APP_USER']}" in openclaw_unit
    assert f"Group={env['APP_GROUP']}" in openclaw_unit
    assert f"Environment=HOME={fake_home}" in openclaw_unit
    assert f"Environment=CLAW_RUNTIME_ROOT={runtime_root}" in openclaw_unit

    nanobot_unit = (systemd_dir / "claw-nanobot@.service").read_text(encoding="utf-8")
    assert f"User={env['APP_USER']}" in nanobot_unit
    assert f"Group={env['APP_GROUP']}" in nanobot_unit
    assert f"Environment=HOME={fake_home}" in nanobot_unit
    assert f"EnvironmentFile={runtime_root}/nanobot/%i/runtime.env" in nanobot_unit


def test_install_native_migrates_legacy_workspace_root_when_target_missing(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    fake_home = Path(env["APP_HOME_OVERRIDE"])
    legacy_root = tmp_path / "legacy" / "workspaces"
    legacy_workspace = legacy_root / "7" / "existing-space"
    legacy_workspace.mkdir(parents=True)
    (legacy_workspace / "README.md").write_text("legacy workspace", encoding="utf-8")

    env["LEGACY_WORKSPACE_ROOT"] = str(legacy_root)
    env_file = Path(env["ENV_FILE"])
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                f"APP_USER={env['APP_USER']}",
                f"APP_GROUP={env['APP_GROUP']}",
                f"RUNTIME_USER={env['APP_USER']}",
                f"RUNTIME_GROUP={env['APP_GROUP']}",
                f"RUNTIME_HOME={fake_home}",
                f"WORKSPACE_ROOT={legacy_root}",
                f"HOST_WORKSPACE_ROOT={legacy_root}",
                "SESSION_SECRET=test-secret",
                "BOOTSTRAP_ADMIN_PASSWORD=test-password",
                "OPENCLAW_BIN=/bin/true",
                "NANOBOT_BIN=/bin/true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_install_shell(
        """
load_existing_env
ensure_single_user_runtime
initialize_paths
migrate_legacy_workspace_root_if_needed
write_env_file
""",
        env,
    )

    new_root = fake_home / "claw"
    assert result.returncode == 0, result.stderr
    assert not legacy_root.exists()
    assert (new_root / "7" / "existing-space" / "README.md").read_text(encoding="utf-8") == "legacy workspace"

    env_text = env_file.read_text(encoding="utf-8")
    assert f"WORKSPACE_ROOT={new_root}" in env_text
    assert f"HOST_WORKSPACE_ROOT={new_root}" in env_text


def test_install_native_rejects_conflicting_legacy_and_new_workspace_roots(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    fake_home = Path(env["APP_HOME_OVERRIDE"])
    legacy_root = tmp_path / "legacy" / "workspaces"
    new_root = fake_home / "claw"
    (legacy_root / "7" / "legacy-space").mkdir(parents=True)
    (new_root / "9" / "new-space").mkdir(parents=True)

    env["LEGACY_WORKSPACE_ROOT"] = str(legacy_root)

    result = run_install_shell(
        """
ensure_single_user_runtime
initialize_paths
migrate_legacy_workspace_root_if_needed
""",
        env,
    )

    assert result.returncode != 0
    assert "both legacy workspace root" in result.stderr


def test_install_native_rejects_separate_runtime_user(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    env["RUNTIME_USER"] = "someone-else"

    result = run_install_shell(
        """
ensure_single_user_runtime
""",
        env,
    )

    assert result.returncode != 0
    assert "RUNTIME_USER must match APP_USER" in result.stderr
