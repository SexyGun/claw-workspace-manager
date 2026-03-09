from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.config import Settings
from app.constants import WORKSPACE_TYPE_BASE, WORKSPACE_TYPE_OPENCLAW
from app.db import get_db
from app.dependencies import (
    get_admin_user,
    get_app_settings,
    get_current_user,
    get_gateway_manager,
    get_openclaw_manager,
    get_workspace_for_user,
)
from app.schemas import (
    OpenClawConfigPayload,
    OpenClawConfigRead,
    RuntimeStatusResponse,
    WorkspaceConfigPayload,
    WorkspaceConfigRead,
    WorkspaceCreate,
    WorkspaceRead,
    WorkspaceSummary,
    WorkspaceTypeRead,
    WorkspaceUpdate,
)
from app.services import config_renderer, workspace as workspace_service
from app.services.gateway import GatewayManager
from app.services.openclaw_runtime import OpenClawRuntimeManager
from app.services.workspace_profiles import get_workspace_profiles

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
workspace_type_router = APIRouter(tags=["workspaces"])


def serialize_runtime_status(instance: models.GatewayInstance | models.OpenClawInstance) -> RuntimeStatusResponse:
    return RuntimeStatusResponse(
        state=instance.state,
        container_name=instance.container_name,
        last_container_id=instance.last_container_id,
        last_error=instance.last_error,
        started_at=instance.started_at,
        stopped_at=instance.stopped_at,
    )


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


def serialize_openclaw_config(workspace: models.Workspace, settings: Settings) -> OpenClawConfigRead:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    openclaw_values = workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
    return OpenClawConfigRead(
        schema=config_renderer.OPENCLAW_SCHEMA,
        values=config_renderer.extract_openclaw_structured_values(openclaw_values),
        raw_json5=config_renderer.openclaw_raw_json(openclaw_values),
        rendered_path=str(local_path / ".openclaw" / "openclaw.json"),
        rendered_at=workspace.config.openclaw_rendered_at,
    )


def load_workspace(db: Session, workspace_id: int) -> models.Workspace | None:
    return db.scalar(
        select(models.Workspace)
        .where(models.Workspace.id == workspace_id)
        .options(
            selectinload(models.Workspace.config),
            selectinload(models.Workspace.gateway_instance),
            selectinload(models.Workspace.openclaw_instance),
        )
    )


def render_workspace_artifacts(db: Session, workspace: models.Workspace, settings: Settings) -> None:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
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
    elif workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW:
        openclaw_payload = config_renderer.render_openclaw_payload(
            workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
        )
        workspace.config.openclaw_rendered_at = config_renderer.write_openclaw_config(
            local_path / ".openclaw" / "openclaw.json",
            openclaw_payload,
        )
    db.add(workspace.config)
    db.commit()


def ensure_workspace_type(workspace: models.Workspace, expected_type: str, label: str) -> None:
    if workspace.workspace_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} endpoints only support {expected_type} workspaces",
        )


@workspace_type_router.get("/workspace-types", response_model=list[WorkspaceTypeRead])
def list_workspace_types(settings: Settings = Depends(get_app_settings)) -> list[WorkspaceTypeRead]:
    profiles = get_workspace_profiles(settings).values()
    return [WorkspaceTypeRead(key=profile.key, label=profile.label, description=profile.description) for profile in profiles]


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
        workspace = workspace_service.create_workspace(db, settings, current_user, payload.name, payload.workspace_type)
        render_workspace_artifacts(db, workspace, settings)
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

    summary = WorkspaceSummary(workspace=WorkspaceRead.model_validate(workspace))
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        summary.nanobot_config = serialize_nanobot_config(workspace, settings)
        summary.gateway_config = serialize_gateway_config(workspace, settings)
        if workspace.gateway_instance:
            summary.gateway_status = serialize_runtime_status(workspace.gateway_instance)
    elif workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW:
        summary.openclaw_config = serialize_openclaw_config(workspace, settings)
        if workspace.openclaw_instance:
            summary.openclaw_status = serialize_runtime_status(workspace.openclaw_instance)
    return summary


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
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "nanobot")
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
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "nanobot")
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
    render_workspace_artifacts(db, workspace, settings)
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
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "gateway")
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
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "gateway")
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
    render_workspace_artifacts(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_gateway_config(workspace, settings)


@router.get("/{workspace_id}/gateway/status", response_model=RuntimeStatusResponse)
def get_gateway_status_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "gateway")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = gateway_manager.status(db, workspace)
    return RuntimeStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/gateway/start", response_model=RuntimeStatusResponse)
def start_gateway_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "gateway")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = gateway_manager.start(db, workspace)
    return RuntimeStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/gateway/stop", response_model=RuntimeStatusResponse)
def stop_gateway_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "gateway")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = gateway_manager.stop(db, workspace)
    return RuntimeStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/gateway/restart", response_model=RuntimeStatusResponse)
def restart_gateway_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "gateway")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = gateway_manager.restart(db, workspace)
    return RuntimeStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.get("/{workspace_id}/openclaw-config", response_model=OpenClawConfigRead)
def get_openclaw_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> OpenClawConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_openclaw_config(workspace, settings)


@router.put("/{workspace_id}/openclaw-config", response_model=OpenClawConfigRead)
def put_openclaw_config_api(
    workspace_id: int,
    payload: OpenClawConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> OpenClawConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None

    try:
        base_config = workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
        if payload.raw_json5 and payload.raw_json5.strip():
            base_config = config_renderer.parse_openclaw_raw_json5(payload.raw_json5)
        merged = config_renderer.merge_openclaw_structured_values(base_config, payload.structured_values)
        merged = config_renderer.validate_openclaw_config(merged)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    workspace.config.openclaw_config_json = merged
    db.add(workspace.config)
    db.commit()
    render_workspace_artifacts(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_openclaw_config(workspace, settings)


@router.get("/{workspace_id}/openclaw/status", response_model=RuntimeStatusResponse)
def get_openclaw_status_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = openclaw_manager.status(db, workspace)
    return RuntimeStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/openclaw/start", response_model=RuntimeStatusResponse)
def start_openclaw_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = openclaw_manager.start(db, workspace)
    return RuntimeStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/openclaw/stop", response_model=RuntimeStatusResponse)
def stop_openclaw_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = openclaw_manager.stop(db, workspace)
    return RuntimeStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.post("/{workspace_id}/openclaw/restart", response_model=RuntimeStatusResponse)
def restart_openclaw_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    runtime = openclaw_manager.restart(db, workspace)
    return RuntimeStatusResponse(
        state=runtime.state,
        container_name=runtime.container_name,
        last_container_id=runtime.container_id,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
    )


@router.get("/admin/all", response_model=list[WorkspaceRead], include_in_schema=False)
def list_all_workspaces_admin(
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceRead]:
    workspaces = db.scalars(select(models.Workspace).order_by(models.Workspace.created_at.desc())).all()
    return [WorkspaceRead.model_validate(workspace) for workspace in workspaces]
