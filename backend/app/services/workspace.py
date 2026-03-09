from __future__ import annotations

import re
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.constants import WORKSPACE_STATUS_READY
from app.services import config_renderer


SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = SLUG_RE.sub("-", lowered).strip("-")
    return slug or "workspace"


def ensure_workspace_roots(settings: Settings) -> None:
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    settings.host_workspace_root.mkdir(parents=True, exist_ok=True)
    settings.workspace_template_root.mkdir(parents=True, exist_ok=True)


def host_path_for_workspace(settings: Settings, owner_user_id: int, slug: str) -> Path:
    return settings.host_workspace_root / str(owner_user_id) / slug


def local_path_from_host_path(settings: Settings, host_path: str | Path) -> Path:
    host_path = Path(host_path).resolve()
    host_root = settings.host_workspace_root.resolve()
    if host_root not in host_path.parents and host_path != host_root:
        raise ValueError("workspace path is outside the allowed root")
    relative = host_path.relative_to(host_root)
    return settings.workspace_root.resolve() / relative


def create_workspace(db: Session, settings: Settings, owner: models.User, name: str) -> models.Workspace:
    slug = slugify(name)
    existing = db.scalar(
        select(models.Workspace).where(models.Workspace.owner_user_id == owner.id, models.Workspace.slug == slug)
    )
    if existing:
        raise ValueError("workspace slug already exists for this user")

    host_path = host_path_for_workspace(settings, owner.id, slug)
    local_path = local_path_from_host_path(settings, host_path)
    if local_path.exists():
        raise ValueError("workspace directory already exists")

    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if any(settings.workspace_template_root.iterdir()):
            shutil.copytree(settings.workspace_template_root, local_path)
        else:
            local_path.mkdir(parents=True, exist_ok=False)
    except Exception as exc:
        if local_path.exists():
            shutil.rmtree(local_path, ignore_errors=True)
        raise ValueError(f"failed to initialize workspace: {exc}") from exc

    (local_path / ".nanobot").mkdir(parents=True, exist_ok=True)

    workspace = models.Workspace(
        owner_user_id=owner.id,
        name=name,
        slug=slug,
        host_path=str(host_path),
        template_version="base-workspace-v1",
        status=WORKSPACE_STATUS_READY,
    )
    db.add(workspace)
    db.flush()

    workspace_config = models.WorkspaceConfig(
        workspace=workspace,
        channel_config_json=config_renderer.default_channel_config(),
        gateway_config_json=config_renderer.default_gateway_config(),
    )
    db.add(workspace_config)
    gateway_instance = models.GatewayInstance(
        workspace=workspace,
        container_name=f"claw-gateway-{workspace.id}",
        image=settings.gateway_image,
        state="stopped",
    )
    db.add(gateway_instance)
    db.commit()
    db.refresh(workspace)
    db.refresh(workspace.config)
    db.refresh(workspace.gateway_instance)
    return workspace
