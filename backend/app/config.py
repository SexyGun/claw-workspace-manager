from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import shlex

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "Claw Workspace Manager"
    api_prefix: str = "/api"
    session_secret: str = "change-me"
    sqlite_path: Path = Path("./.data/sqlite/app.db")
    workspace_root: Path = Path("./.data/workspaces")
    host_workspace_root: Path = Path("./.data/workspaces")
    runtime_state_root: Path = Path("./.data/runtime")
    workspace_template_root: Path = Path("./deploy/templates/base-workspace")
    openclaw_workspace_template_root: Path = Path("./deploy/templates/openclaw-workspace")
    systemctl_command: str = "systemctl"
    systemctl_use_sudo: bool = False
    sudo_command: str = "sudo"
    nanobot_unit_template: str = "claw-nanobot@{workspace_id}.service"
    openclaw_shared_unit: str = "claw-openclaw.service"
    runtime_host: str = "127.0.0.1"
    nanobot_port_base: int = 18080
    openclaw_gateway_port: int = 7331
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_path}"

    @property
    def systemctl_command_argv(self) -> list[str]:
        return shlex.split(self.systemctl_command)

    @property
    def sudo_command_argv(self) -> list[str]:
        return shlex.split(self.sudo_command)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
