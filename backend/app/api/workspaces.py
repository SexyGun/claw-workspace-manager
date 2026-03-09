from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.config import Settings
from app.db import get_db
from app.dependencies import get_admin_user, get_app_settings, get_current_user, get_gateway_manager, get_workspace_for_user
from app.schemas import (
    GatewayStatusResponse,
    MessageResponse,
    WorkspaceConfigPayload,
    WorkspaceConfigRead,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceSummary,
    WorkspaceUpdate,
)
from app.services import config_renderer, workspace as workspace_service
from app.services.gateway import GatewayManager

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def serialize_nanobot_config(workspace: models.Workspace, settings: Settings) -> WorkspaceConfigRead:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    return WorkspaceConfigRead(
        schema=config_renderer.CHANNEL_SCHEMA,
        values=config_renderer.mask_channel_config(workspace.config.channel_config_json),
        rendered_path=str(local_path / ".nanobot" / "config.json"),
        rendered_at=workspace.config.nanobot_rendered_at,
    )


def serialize_gateway_config(workspace: models.Workspace, settings: Settings) -> WorkspaceConfigRead:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    return WorkspaceConfigRead(
        schema=config_renderer.GATEWAY_SCHEMA,
        values=workspace.config.gateway_config_json or config_renderer.default_gateway_config(),
        rendered_path=str(local_path / ".nanobot" / "gateway.yaml"),
        rendered_at=workspace.config.gateway_rendered_at,
    )


def serialize_gateway_status(workspace: models.Workspace) -> GatewayStatusResponse:
    instance = workspace.gateway_instance
    return GatewayStatusResponse(
        state=instance.state,
        container_name=instance.container_name,
        last_container_id=instance.last_container_id,
        last_error=instance.last_error,
        started_at=instance.started_at,
        stopped_at=instance.stopped_at,
    )


def load_workspace(db: Session, workspace_id: int) -> models.Workspace | None:
    return db.scalar(
        select(models.Workspace)
        .where(models.Workspace.id == workspace_id)
        .options(
            selectinload(models.Workspace.config),
            selectinload(models.Workspace.gateway_instance),
        )
    )


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceRead]:
    query = select(models.Workspace).order_by(models.Workspace.created_at.desc())
    if current_user.role != "admin":
        query = query.where(models.Workspace.owner_user_id == current_user.id)
    workspaces = db.scalars(query).all()
    return [WorkspaceRead.model_validate(workspace) for workspace in workspaces]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace_api(
    payload: WorkspaceCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceRead:
    try:
        workspace = workspace_service.create_workspace(db, settings, current_user, payload.name)
        render_all_configs(db, workspace, settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkspaceRead.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceSummary)
def get_workspace_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceSummary:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return WorkspaceSummary(
        workspace=WorkspaceRead.model_validate(workspace),
        nanobot_config=serialize_nanobot_config(workspace, settings),
        gateway_config=serialize_gateway_config(workspace, settings),
        gateway_status=serialize_gateway_status(workspace),
    )


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
def update_workspace_api(
    workspace_id: int,
    payload: WorkspaceUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    if payload.name is not None:
        workspace.name = payload.name
    if payload.status is not None:
        workspace.status = payload.status
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return WorkspaceRead.model_validate(workspace)


@router.get("/{workspace_id}/nanobot-config", response_model=WorkspaceConfigRead)
def get_nanobot_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_nanobot_config(workspace, settings)


@router.put("/{workspace_id}/nanobot-config", response_model=WorkspaceConfigRead)
def put_nanobot_config_api(
    workspace_id: int,
    payload: WorkspaceConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None

    try:
        merged = config_renderer.merge_channel_config(workspace.config.channel_config_json, payload.values)
        config_renderer.validate_channel_config(merged)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    workspace.config.channel_config_json = merged
    db.add(workspace.config)
    db.commit()
    render_all_configs(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_nanobot_config(workspace, settings)


@router.get("/{workspace_id}/gateway-config", response_model=WorkspaceConfigRead)
def get_gateway_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_gateway_config(workspace, settings)


@router.put("/{workspace_id}/gateway-config", response_model=WorkspaceConfigRead)
def put_gateway_config_api(
    workspace_id: int,
    payload: WorkspaceConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None

    try:
        merged = config_renderer.merge_gateway_config(workspace.config.gateway_config_json, payload.values)
        config_renderer.validate_gateway_config(merged)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    workspace.config.gateway_config_json = merged
    db.add(workspace.config)
    db.commit()
    render_all_configs(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_gateway_config(workspace, settings)


@router.get("/{workspace_id}/gateway/status", response_model=GatewayStatusResponse)
def get_gateway_status_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> GatewayStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = gateway_manager.status(db, workspace)
    return GatewayStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/gateway/start", response_model=GatewayStatusResponse)
def start_gateway_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> GatewayStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = gateway_manager.start(db, workspace)
    return GatewayStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/gateway/stop", response_model=GatewayStatusResponse)
def stop_gateway_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> GatewayStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = gateway_manager.stop(db, workspace)
    return GatewayStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/gateway/restart", response_model=GatewayStatusResponse)
def restart_gateway_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> GatewayStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = gateway_manager.restart(db, workspace)
    return GatewayStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


def render_all_configs(db: Session, workspace: models.Workspace, settings: Settings) -> None:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    nanobot_payload = config_renderer.render_nanobot_payload(
        workspace.name,
        workspace.slug,
        workspace.config.channel_config_json or config_renderer.default_channel_config(),
    )
    workspace.config.nanobot_rendered_at = config_renderer.write_nanobot_config(
        local_path / ".nanobot" / "config.json",
        nanobot_payload,
    )
    gateway_payload = config_renderer.render_gateway_payload(
        workspace.id,
        workspace.name,
        workspace.config.gateway_config_json or config_renderer.default_gateway_config(),
        settings,
    )
    workspace.config.gateway_rendered_at = config_renderer.write_gateway_config(
        local_path / ".nanobot" / "gateway.yaml",
        gateway_payload,
    )
    db.add(workspace.config)
    db.commit()


@router.get("/admin/all", response_model=list[WorkspaceRead], include_in_schema=False)
def list_all_workspaces_admin(_: models.User = Depends(get_admin_user), db: Session = Depends(get_db)) -> list[WorkspaceRead]:
    workspaces = db.scalars(select(models.Workspace).order_by(models.Workspace.created_at.desc())).all()
    return [WorkspaceRead.model_validate(workspace) for workspace in workspaces]
