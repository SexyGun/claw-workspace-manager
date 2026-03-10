from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.config import Settings
from app.constants import WORKSPACE_TYPE_BASE, WORKSPACE_TYPE_OPENCLAW
from app.services import config_renderer, workspace as workspace_service


def load_workspace(db: Session, workspace_id: int) -> models.Workspace | None:
    return db.scalar(
        select(models.Workspace)
        .where(models.Workspace.id == workspace_id)
        .options(selectinload(models.Workspace.config), selectinload(models.Workspace.runtime))
    )


def load_openclaw_workspaces(db: Session) -> list[models.Workspace]:
    return list(
        db.scalars(
            select(models.Workspace)
            .where(models.Workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW)
            .options(selectinload(models.Workspace.config))
        ).all()
    )


def render_openclaw_service_artifacts(db: Session, settings: Settings) -> None:
    workspaces = load_openclaw_workspaces(db)
    aggregate_items: list[dict[str, object]] = []
    for workspace in workspaces:
        local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
        openclaw_workspace_path = str(local_path / ".openclaw" / "workspace")
        openclaw_payload = config_renderer.render_openclaw_workspace_payload(
            workspace.config.openclaw_config_json or config_renderer.default_openclaw_config(),
            workspace_path=openclaw_workspace_path,
        )
        workspace.config.openclaw_rendered_at = config_renderer.write_openclaw_config(
            local_path / ".openclaw" / "openclaw.json",
            openclaw_payload,
        )
        channel_payload = config_renderer.validate_openclaw_channel_config(
            workspace.config.openclaw_channel_json or config_renderer.default_openclaw_channel_config()
        )
        (local_path / ".openclaw").mkdir(parents=True, exist_ok=True)
        (local_path / ".openclaw" / "channel.json").write_text(
            json.dumps(channel_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        aggregate_items.append(
            {
                "workspace": workspace,
                "workspace_path": openclaw_workspace_path,
                "openclaw_config": workspace.config.openclaw_config_json or config_renderer.default_openclaw_config(),
                "openclaw_channel": workspace.config.openclaw_channel_json or config_renderer.default_openclaw_channel_config(),
                "openclaw_binding": workspace.config.openclaw_binding_json or config_renderer.default_openclaw_binding_config(),
            }
        )
        db.add(workspace.config)

    aggregate_payload = config_renderer.render_openclaw_aggregate_payload(aggregate_items, settings)
    config_renderer.write_openclaw_aggregate_config(
        settings.runtime_state_root / "openclaw" / "openclaw.json",
        aggregate_payload,
    )
    db.commit()


def render_workspace_artifacts(db: Session, workspace: models.Workspace, settings: Settings) -> None:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        runtime_root = settings.runtime_state_root / "nanobot" / str(workspace.id)
        workspace_path = str(Path(workspace.host_path) / "workspace")
        source_config_path = local_path / ".nanobot" / "config.json"
        gateway_config = config_renderer.validate_gateway_config(
            workspace.config.gateway_config_json or config_renderer.default_gateway_config()
        )
        base_config = config_renderer.load_nanobot_instance_config(source_config_path)
        nanobot_payload = config_renderer.render_nanobot_config_payload(
            base_config,
            workspace.config.channel_config_json or config_renderer.default_channel_config(),
            workspace_path=workspace_path,
            gateway_host=gateway_config["listen_host"],
            gateway_port=gateway_config["listen_port"],
        )
        workspace.config.nanobot_rendered_at = config_renderer.write_nanobot_config(
            source_config_path,
            nanobot_payload,
        )
        config_renderer.write_nanobot_config(runtime_root / "config.json", nanobot_payload)
        workspace.config.gateway_rendered_at = config_renderer.write_runtime_env(
            runtime_root / "runtime.env",
            {
                "NANOBOT_CONFIG_PATH": runtime_root / "config.json",
                "NANOBOT_WORKSPACE_PATH": workspace_path,
                "NANOBOT_PORT": gateway_config["listen_port"],
            },
        )
        db.add(workspace.config)
        db.commit()
        return

    if workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW:
        render_openclaw_service_artifacts(db, settings)


def ensure_workspace_type(workspace: models.Workspace, expected_type: str, label: str) -> None:
    if workspace.workspace_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} endpoints only support {expected_type} workspaces",
        )


def mark_workspace_runtime_for_restart(db: Session, workspace: models.Workspace) -> None:
    runtime = workspace.runtime
    if runtime is None:
        return
    if runtime.state not in {"running", "starting", "stopping"}:
        return
    runtime.needs_restart = True
    db.add(runtime)
