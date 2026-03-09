from __future__ import annotations

import re
import shutil
from pathlib import Path

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.constants import (
    RUNTIME_CONTROLLER_SYSTEMD,
    RUNTIME_KIND_NANOBOT,
    RUNTIME_SCOPE_WORKSPACE,
    RUNTIME_STATE_STOPPED,
    WORKSPACE_STATUS_READY,
    WORKSPACE_TYPE_BASE,
    WORKSPACE_TYPE_OPENCLAW,
)
from app.services import config_renderer
from app.services.workspace_profiles import get_workspace_profile


SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = SLUG_RE.sub("-", lowered).strip("-")
    return slug or "workspace"


def ensure_workspace_roots(settings: Settings) -> None:
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    settings.host_workspace_root.mkdir(parents=True, exist_ok=True)
    settings.runtime_state_root.mkdir(parents=True, exist_ok=True)
    settings.workspace_template_root.mkdir(parents=True, exist_ok=True)
    settings.openclaw_workspace_template_root.mkdir(parents=True, exist_ok=True)


def host_path_for_workspace(settings: Settings, owner_user_id: int, slug: str) -> Path:
    return settings.host_workspace_root / str(owner_user_id) / slug


def local_path_from_host_path(settings: Settings, host_path: str | Path) -> Path:
    host_path = Path(host_path).resolve()
    host_root = settings.host_workspace_root.resolve()
    if host_root not in host_path.parents and host_path != host_root:
        raise ValueError("workspace path is outside the allowed root")
    relative = host_path.relative_to(host_root)
    return settings.workspace_root.resolve() / relative


def allocate_workspace_port(db: Session, settings: Settings) -> int:
    current_max = db.scalar(select(func.max(models.WorkspaceRuntime.listen_port)))
    if current_max is None or current_max < settings.nanobot_port_base:
        return settings.nanobot_port_base
    return current_max + 1


def create_workspace(
    db: Session,
    settings: Settings,
    owner: models.User,
    name: str,
    workspace_type: str = WORKSPACE_TYPE_BASE,
) -> models.Workspace:
    profile = get_workspace_profile(settings, workspace_type)
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
        if any(profile.template_root.iterdir()):
            shutil.copytree(profile.template_root, local_path)
        else:
            local_path.mkdir(parents=True, exist_ok=False)
    except Exception as exc:
        if local_path.exists():
            shutil.rmtree(local_path, ignore_errors=True)
        raise ValueError(f"failed to initialize workspace: {exc}") from exc

    if workspace_type == WORKSPACE_TYPE_BASE:
        (local_path / ".nanobot").mkdir(parents=True, exist_ok=True)
    elif workspace_type == WORKSPACE_TYPE_OPENCLAW:
        (local_path / ".openclaw" / "workspace").mkdir(parents=True, exist_ok=True)

    workspace = models.Workspace(
        owner_user_id=owner.id,
        name=name,
        slug=slug,
        workspace_type=workspace_type,
        host_path=str(host_path),
        template_version=profile.template_version,
        status=WORKSPACE_STATUS_READY,
    )
    db.add(workspace)
    db.flush()

    openclaw_config = {}
    openclaw_channel_config = {}
    openclaw_binding_config = {}
    if workspace_type == WORKSPACE_TYPE_OPENCLAW:
        openclaw_config = config_renderer.load_openclaw_template_config(local_path / ".openclaw" / "openclaw.json")
        openclaw_channel_config = config_renderer.default_openclaw_channel_config()
        openclaw_binding_config = config_renderer.default_openclaw_binding_config()
    gateway_config = config_renderer.default_gateway_config()
    if workspace_type == WORKSPACE_TYPE_BASE:
        gateway_config["listen_host"] = settings.runtime_host
        gateway_config["listen_port"] = allocate_workspace_port(db, settings)

    workspace_config = models.WorkspaceConfig(
        workspace=workspace,
        channel_config_json=config_renderer.default_channel_config() if workspace_type == WORKSPACE_TYPE_BASE else {},
        gateway_config_json=gateway_config if workspace_type == WORKSPACE_TYPE_BASE else {},
        openclaw_config_json=openclaw_config,
        openclaw_channel_json=openclaw_channel_config,
        openclaw_binding_json=openclaw_binding_config,
    )
    db.add(workspace_config)

    if workspace_type == WORKSPACE_TYPE_BASE:
        db.add(
            models.WorkspaceRuntime(
                workspace=workspace,
                runtime_kind=RUNTIME_KIND_NANOBOT,
                scope=RUNTIME_SCOPE_WORKSPACE,
                controller_kind=RUNTIME_CONTROLLER_SYSTEMD,
                unit_name=settings.nanobot_unit_template.format(workspace_id=workspace.id),
                listen_port=gateway_config["listen_port"],
                state=RUNTIME_STATE_STOPPED,
            )
        )

    db.commit()
    db.refresh(workspace)
    db.refresh(workspace.config)
    if workspace_type == WORKSPACE_TYPE_BASE and workspace.runtime is not None:
        db.refresh(workspace.runtime)
    return workspace
