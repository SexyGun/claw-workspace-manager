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
    data_root = fake_home / "claw"
    workspace_root = data_root
    runtime_root = data_root / "runtime"
    sqlite_path = data_root / "sqlite" / "app.db"
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
    assert f"DATA_ROOT={data_root}" in env_text
    assert f"SQLITE_PATH={sqlite_path}" in env_text
    assert f"RUNTIME_STATE_ROOT={runtime_root}" in env_text
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


def test_install_native_migrates_legacy_data_root_when_target_missing(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    fake_home = Path(env["APP_HOME_OVERRIDE"])
    legacy_data_root = tmp_path / "legacy"
    legacy_root = legacy_data_root / "workspaces"
    legacy_workspace = legacy_root / "7" / "existing-space"
    legacy_runtime_root = legacy_data_root / "runtime"
    legacy_sqlite_dir = legacy_data_root / "sqlite"
    legacy_workspace.mkdir(parents=True)
    legacy_runtime_root.mkdir(parents=True)
    legacy_sqlite_dir.mkdir(parents=True)
    (legacy_workspace / "README.md").write_text("legacy workspace", encoding="utf-8")
    (legacy_runtime_root / "openclaw.json").write_text("legacy runtime", encoding="utf-8")
    (legacy_sqlite_dir / "app.db").write_text("legacy sqlite", encoding="utf-8")

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
                f"SQLITE_PATH={legacy_data_root / 'sqlite' / 'app.db'}",
                f"WORKSPACE_ROOT={legacy_root}",
                f"HOST_WORKSPACE_ROOT={legacy_root}",
                f"RUNTIME_STATE_ROOT={legacy_data_root / 'runtime'}",
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
migrate_legacy_data_root_if_needed
write_env_file
""",
        env,
    )

    new_root = fake_home / "claw"
    assert result.returncode == 0, result.stderr
    assert not legacy_data_root.exists()
    assert (new_root / "7" / "existing-space" / "README.md").read_text(encoding="utf-8") == "legacy workspace"
    assert (new_root / "runtime" / "openclaw.json").read_text(encoding="utf-8") == "legacy runtime"
    assert (new_root / "sqlite" / "app.db").read_text(encoding="utf-8") == "legacy sqlite"

    env_text = env_file.read_text(encoding="utf-8")
    assert f"DATA_ROOT={new_root}" in env_text
    assert f"SQLITE_PATH={new_root / 'sqlite' / 'app.db'}" in env_text
    assert f"WORKSPACE_ROOT={new_root}" in env_text
    assert f"HOST_WORKSPACE_ROOT={new_root}" in env_text
    assert f"RUNTIME_STATE_ROOT={new_root / 'runtime'}" in env_text


def test_install_native_ignores_legacy_runtime_identity_from_existing_env(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    fake_home = Path(env["APP_HOME_OVERRIDE"])
    data_root = fake_home / "claw"
    env_file = Path(env["ENV_FILE"])
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                f"APP_USER={env['APP_USER']}",
                f"APP_GROUP={env['APP_GROUP']}",
                "RUNTIME_USER=legacy-runtime",
                "RUNTIME_GROUP=legacy-group",
                "RUNTIME_HOME=/home/legacy-runtime",
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
write_env_file
""",
        env,
    )

    assert result.returncode == 0, result.stderr
    env_text = env_file.read_text(encoding="utf-8")
    assert f"RUNTIME_USER={env['APP_USER']}" in env_text
    assert f"RUNTIME_GROUP={env['APP_GROUP']}" in env_text
    assert f"RUNTIME_HOME={fake_home}" in env_text
    assert f"DATA_ROOT={data_root}" in env_text
    assert "ignoring legacy RUNTIME_USER=legacy-runtime" in result.stderr
    assert "ignoring legacy RUNTIME_GROUP=legacy-group" in result.stderr
    assert "ignoring legacy RUNTIME_HOME=/home/legacy-runtime" in result.stderr


def test_install_native_preserves_explicit_custom_data_root_from_existing_env(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    custom_root = tmp_path / "custom-data-root"
    env_file = Path(env["ENV_FILE"])
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                f"DATA_ROOT={custom_root}",
                f"APP_USER={env['APP_USER']}",
                f"APP_GROUP={env['APP_GROUP']}",
                f"RUNTIME_USER={env['APP_USER']}",
                f"RUNTIME_GROUP={env['APP_GROUP']}",
                f"RUNTIME_HOME={env['APP_HOME_OVERRIDE']}",
                f"SQLITE_PATH={custom_root / 'sqlite' / 'app.db'}",
                f"WORKSPACE_ROOT={custom_root}",
                f"HOST_WORKSPACE_ROOT={custom_root}",
                f"RUNTIME_STATE_ROOT={custom_root / 'runtime'}",
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
write_env_file
""",
        env,
    )

    assert result.returncode == 0, result.stderr
    env_text = env_file.read_text(encoding="utf-8")
    assert f"DATA_ROOT={custom_root}" in env_text
    assert f"SQLITE_PATH={custom_root / 'sqlite' / 'app.db'}" in env_text
    assert f"WORKSPACE_ROOT={custom_root}" in env_text
    assert f"HOST_WORKSPACE_ROOT={custom_root}" in env_text
    assert f"RUNTIME_STATE_ROOT={custom_root / 'runtime'}" in env_text


def test_install_native_migrates_previous_managed_data_root_when_app_user_changes(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    old_home = tmp_path / "old-service-home"
    new_home = Path(env["APP_HOME_OVERRIDE"])
    old_root = old_home / "claw"
    old_workspace = old_root / "12" / "migrated-space"
    old_runtime_root = old_root / "runtime"
    old_sqlite_dir = old_root / "sqlite"
    old_workspace.mkdir(parents=True)
    old_runtime_root.mkdir(parents=True)
    old_sqlite_dir.mkdir(parents=True)
    (old_workspace / "README.md").write_text("migrate me", encoding="utf-8")
    (old_runtime_root / "state.json").write_text("runtime", encoding="utf-8")
    (old_sqlite_dir / "app.db").write_text("sqlite", encoding="utf-8")

    env_file = Path(env["ENV_FILE"])
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                f"DATA_ROOT={old_root}",
                "APP_USER=legacy-manager",
                "APP_GROUP=legacy-manager",
                "RUNTIME_USER=legacy-manager",
                "RUNTIME_GROUP=legacy-manager",
                f"RUNTIME_HOME={old_home}",
                f"SQLITE_PATH={old_root / 'sqlite' / 'app.db'}",
                f"WORKSPACE_ROOT={old_root}",
                f"HOST_WORKSPACE_ROOT={old_root}",
                f"RUNTIME_STATE_ROOT={old_root / 'runtime'}",
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
migrate_previous_managed_data_root_if_needed
write_env_file
""",
        env,
    )

    new_root = new_home / "claw"
    assert result.returncode == 0, result.stderr
    assert not old_root.exists()
    assert (new_root / "12" / "migrated-space" / "README.md").read_text(encoding="utf-8") == "migrate me"
    assert (new_root / "runtime" / "state.json").read_text(encoding="utf-8") == "runtime"
    assert (new_root / "sqlite" / "app.db").read_text(encoding="utf-8") == "sqlite"

    env_text = env_file.read_text(encoding="utf-8")
    assert f"DATA_ROOT={new_root}" in env_text
    assert f"WORKSPACE_ROOT={new_root}" in env_text
    assert f"HOST_WORKSPACE_ROOT={new_root}" in env_text
    assert f"SQLITE_PATH={new_root / 'sqlite' / 'app.db'}" in env_text
    assert f"RUNTIME_STATE_ROOT={new_root / 'runtime'}" in env_text
    assert "migrating data root from" in result.stdout


def test_install_native_uses_current_sudo_user_without_app_env_overrides(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    username, group = current_identity()
    old_home = tmp_path / "old-service-home"
    new_home = Path(env["APP_HOME_OVERRIDE"])
    old_root = old_home / "claw"
    old_workspace = old_root / "22" / "sudo-user-space"
    old_runtime_root = old_root / "runtime"
    old_workspace.mkdir(parents=True)
    old_runtime_root.mkdir(parents=True)
    (old_workspace / "README.md").write_text("current user migration", encoding="utf-8")
    (old_runtime_root / "state.json").write_text("runtime", encoding="utf-8")

    env.pop("APP_USER")
    env.pop("APP_GROUP")
    env["SUDO_USER"] = username

    env_file = Path(env["ENV_FILE"])
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                f"DATA_ROOT={old_root}",
                "APP_USER=legacy-manager",
                "APP_GROUP=legacy-manager",
                "RUNTIME_USER=legacy-manager",
                "RUNTIME_GROUP=legacy-manager",
                f"RUNTIME_HOME={old_home}",
                f"SQLITE_PATH={old_root / 'sqlite' / 'app.db'}",
                f"WORKSPACE_ROOT={old_root}",
                f"HOST_WORKSPACE_ROOT={old_root}",
                f"RUNTIME_STATE_ROOT={old_root / 'runtime'}",
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
migrate_previous_managed_data_root_if_needed
write_env_file
""",
        env,
    )

    new_root = new_home / "claw"
    assert result.returncode == 0, result.stderr
    assert not old_root.exists()
    assert (new_root / "22" / "sudo-user-space" / "README.md").read_text(encoding="utf-8") == "current user migration"
    assert (new_root / "runtime" / "state.json").read_text(encoding="utf-8") == "runtime"

    env_text = env_file.read_text(encoding="utf-8")
    assert f"APP_USER={username}" in env_text
    assert f"APP_GROUP={group}" in env_text
    assert f"DATA_ROOT={new_root}" in env_text
    assert f"WORKSPACE_ROOT={new_root}" in env_text
    assert f"HOST_WORKSPACE_ROOT={new_root}" in env_text


def test_install_native_merges_disjoint_legacy_and_new_workspace_roots(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    fake_home = Path(env["APP_HOME_OVERRIDE"])
    legacy_root = tmp_path / "legacy" / "workspaces"
    new_root = fake_home / "claw"
    (legacy_root / "7" / "legacy-space").mkdir(parents=True)
    (new_root / "9" / "new-space").mkdir(parents=True)
    (new_root / "runtime").mkdir(parents=True)
    (legacy_root / "7" / "legacy-space" / "README.md").write_text("legacy", encoding="utf-8")
    (new_root / "9" / "new-space" / "README.md").write_text("new", encoding="utf-8")
    (new_root / "runtime" / "state.json").write_text("new runtime", encoding="utf-8")

    env["LEGACY_WORKSPACE_ROOT"] = str(legacy_root)

    result = run_install_shell(
        """
ensure_single_user_runtime
initialize_paths
migrate_legacy_data_root_if_needed
""",
        env,
    )

    assert result.returncode == 0, result.stderr
    assert not legacy_root.exists()
    assert (new_root / "7" / "legacy-space" / "README.md").read_text(encoding="utf-8") == "legacy"
    assert (new_root / "9" / "new-space" / "README.md").read_text(encoding="utf-8") == "new"
    assert (new_root / "runtime" / "state.json").read_text(encoding="utf-8") == "new runtime"
    assert "merging workspace root from" in result.stdout


def test_install_native_rejects_conflicting_legacy_and_new_workspace_roots(tmp_path: Path) -> None:
    env = base_env(tmp_path)
    fake_home = Path(env["APP_HOME_OVERRIDE"])
    legacy_root = tmp_path / "legacy" / "workspaces"
    new_root = fake_home / "claw"
    (legacy_root / "7" / "shared-space").mkdir(parents=True)
    (new_root / "7" / "shared-space").mkdir(parents=True)

    env["LEGACY_WORKSPACE_ROOT"] = str(legacy_root)

    result = run_install_shell(
        """
ensure_single_user_runtime
initialize_paths
migrate_legacy_data_root_if_needed
""",
        env,
    )

    assert result.returncode != 0
    assert "workspace root migration conflict for 7/shared-space" in result.stderr


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
