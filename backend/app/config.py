from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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
    workspace_template_root: Path = Path("./deploy/templates/base-workspace")
    openclaw_workspace_template_root: Path = Path("./deploy/templates/openclaw-workspace")
    gateway_image: str = "ghcr.io/example/nanobot-gateway:latest"
    gateway_workspace_mount: str = "/workspace"
    gateway_config_path: str = "/workspace/.nanobot/gateway.yaml"
    nanobot_config_path: str = "/workspace/.nanobot/config.json"
    openclaw_image: str = "ghcr.io/example/openclaw:latest"
    openclaw_workspace_mount: str = "/workspace"
    gateway_stop_timeout: int = 10
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
