from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.config import Settings
from app.constants import (
    RUNTIME_CONTROLLER_SYSTEMD,
    RUNTIME_KIND_OPENCLAW,
    RUNTIME_SCOPE_ROUTE,
    RUNTIME_SCOPE_SHARED,
    RUNTIME_STATE_CONFIGURED,
    RUNTIME_STATE_INACTIVE,
    WORKSPACE_TYPE_BASE,
    WORKSPACE_TYPE_OPENCLAW,
)
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
    OpenClawChannelConfigPayload,
    OpenClawConfigPayload,
    OpenClawConfigRead,
    OpenClawRouteRead,
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
from app.services.runtime_control import RuntimeStatus
from app.services.workspace_profiles import get_workspace_profiles

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
workspace_type_router = APIRouter(tags=["workspaces"])


def serialize_runtime_status(runtime: RuntimeStatus) -> RuntimeStatusResponse:
    return RuntimeStatusResponse(
        state=runtime.state,
        scope=runtime.scope,
        controller_kind=runtime.controller_kind,
        unit_name=runtime.unit_name,
        process_id=runtime.process_id,
        listen_port=runtime.listen_port,
        config_path=runtime.config_path,
        workspace_path=runtime.workspace_path,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
        needs_restart=runtime.needs_restart,
    )


def serialize_workspace_runtime(runtime: models.WorkspaceRuntime | None) -> RuntimeStatusResponse | None:
    if runtime is None:
        return None
    return RuntimeStatusResponse(
        state=runtime.state,
        scope=runtime.scope,
        controller_kind=runtime.controller_kind,
        unit_name=runtime.unit_name,
        process_id=runtime.process_id,
        listen_port=runtime.listen_port,
        config_path=None,
        workspace_path=None,
        last_error=runtime.last_error,
        started_at=runtime.started_at,
        stopped_at=runtime.stopped_at,
        needs_restart=runtime.needs_restart,
    )


def workspace_activation_state(runtime: models.WorkspaceRuntime | None) -> str | None:
    if runtime is None:
        return None
    if runtime.state == "error":
        return "error"
    if runtime.state in {"running", "starting", "stopping"}:
        return "active"
    return "inactive"


def serialize_workspace(workspace: models.Workspace) -> WorkspaceRead:
    return WorkspaceRead.model_validate(
        {
            "id": workspace.id,
            "owner_user_id": workspace.owner_user_id,
            "name": workspace.name,
            "slug": workspace.slug,
            "workspace_type": workspace.workspace_type,
            "host_path": workspace.host_path,
            "template_version": workspace.template_version,
            "status": workspace.status,
            "activation_state": workspace_activation_state(workspace.runtime),
            "listen_port": workspace.runtime.listen_port if workspace.runtime else None,
            "created_at": workspace.created_at,
        }
    )


def serialize_nanobot_config(workspace: models.Workspace, settings: Settings) -> WorkspaceConfigRead:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    return WorkspaceConfigRead(
        schema=config_renderer.CHANNEL_SCHEMA,
        values=config_renderer.mask_channel_config(workspace.config.channel_config_json),
        rendered_path=str(local_path / ".nanobot" / "config.json"),
        rendered_at=workspace.config.nanobot_rendered_at,
        warnings=config_renderer.channel_config_warnings(workspace.config.channel_config_json),
    )


def serialize_nanobot_provider_config(workspace: models.Workspace, settings: Settings) -> WorkspaceConfigRead:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    base_config = config_renderer.load_nanobot_instance_config(local_path / ".nanobot" / "config.json")
    return WorkspaceConfigRead(
        schema=config_renderer.PROVIDER_SCHEMA,
        values=config_renderer.mask_provider_config(base_config),
        rendered_path=str(local_path / ".nanobot" / "config.json"),
        rendered_at=workspace.config.nanobot_rendered_at,
    )


def serialize_nanobot_agent_config(workspace: models.Workspace, settings: Settings) -> WorkspaceConfigRead:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    base_config = config_renderer.load_nanobot_instance_config(local_path / ".nanobot" / "config.json")
    return WorkspaceConfigRead(
        schema=config_renderer.AGENT_DEFAULTS_SCHEMA,
        values=config_renderer.extract_agent_defaults_config(base_config),
        rendered_path=str(local_path / ".nanobot" / "config.json"),
        rendered_at=workspace.config.nanobot_rendered_at,
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


def serialize_openclaw_channel_config(workspace: models.Workspace, settings: Settings) -> WorkspaceConfigRead:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    return WorkspaceConfigRead(
        schema=config_renderer.OPENCLAW_CHANNEL_SCHEMA,
        values=config_renderer.mask_openclaw_channel_config(workspace.config.openclaw_channel_json),
        rendered_path=str(local_path / ".openclaw" / "channel.json"),
        rendered_at=workspace.config.openclaw_rendered_at,
    )


def serialize_openclaw_route(workspace: models.Workspace) -> OpenClawRouteRead:
    route = config_renderer.build_openclaw_route(
        workspace.config.openclaw_channel_json or config_renderer.default_openclaw_channel_config(),
        workspace.config.openclaw_binding_json or config_renderer.default_openclaw_binding_config(),
        workspace.id,
    )
    return OpenClawRouteRead(
        agent_id=route["agent_id"],
        channel=route["channel"],
        account_id=route["account_id"],
        enabled=route["enabled"],
    )


def serialize_openclaw_route_runtime(workspace: models.Workspace) -> RuntimeStatusResponse:
    route = serialize_openclaw_route(workspace)
    return RuntimeStatusResponse(
        state=RUNTIME_STATE_CONFIGURED if route.enabled else RUNTIME_STATE_INACTIVE,
        scope=RUNTIME_SCOPE_ROUTE,
        controller_kind=RUNTIME_KIND_OPENCLAW,
        unit_name=None,
        process_id=None,
        listen_port=None,
        config_path=None,
        workspace_path=None,
        last_error=None,
        started_at=None,
        stopped_at=None,
        needs_restart=False,
    )


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
        openclaw_payload = config_renderer.render_openclaw_workspace_payload(
            workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
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
                "workspace_path": str(local_path / ".openclaw" / "workspace"),
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
    elif workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW:
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


@workspace_type_router.get("/workspace-types", response_model=list[WorkspaceTypeRead])
def list_workspace_types(settings: Settings = Depends(get_app_settings)) -> list[WorkspaceTypeRead]:
    profiles = get_workspace_profiles(settings).values()
    return [WorkspaceTypeRead(key=profile.key, label=profile.label, description=profile.description) for profile in profiles]


@router.get("", response_model=list[WorkspaceRead])
def list_workspaces(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceRead]:
    query = select(models.Workspace).options(selectinload(models.Workspace.runtime)).order_by(models.Workspace.created_at.desc())
    if current_user.role != "admin":
        query = query.where(models.Workspace.owner_user_id == current_user.id)
    workspaces = db.scalars(query).all()
    return [serialize_workspace(workspace) for workspace in workspaces]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace_api(
    payload: WorkspaceCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> WorkspaceRead:
    workspace: models.Workspace | None = None
    try:
        workspace = workspace_service.create_workspace(db, settings, current_user, payload.name, payload.workspace_type)
        render_workspace_artifacts(db, workspace, settings)
        if workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW:
            openclaw_manager.reload_if_running(db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        if workspace is not None:
            workspace_service.delete_workspace(db, settings, workspace)
            if workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW:
                render_openclaw_service_artifacts(db, settings)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workspace created but post-processing failed; partial data has been cleaned up.",
        ) from exc
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_workspace(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceSummary)
def get_workspace_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> WorkspaceSummary:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None

    summary = WorkspaceSummary(workspace=serialize_workspace(workspace))
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        summary.nanobot_config = serialize_nanobot_config(workspace, settings)
        summary.nanobot_agent_config = serialize_nanobot_agent_config(workspace, settings)
        summary.nanobot_provider_config = serialize_nanobot_provider_config(workspace, settings)
        summary.runtime_status = serialize_runtime_status(gateway_manager.status(db, workspace))
    elif workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW:
        summary.openclaw_config = serialize_openclaw_config(workspace, settings)
        summary.openclaw_channel_config = serialize_openclaw_channel_config(workspace, settings)
        summary.openclaw_route = serialize_openclaw_route(workspace)
        summary.runtime_status = serialize_openclaw_route_runtime(workspace)
        summary.shared_runtime_status = serialize_runtime_status(openclaw_manager.service_status(db))
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
    return serialize_workspace(workspace)


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
    mark_workspace_runtime_for_restart(db, workspace)
    db.add(workspace.config)
    db.commit()
    render_workspace_artifacts(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_nanobot_config(workspace, settings)


@router.get("/{workspace_id}/provider-config", response_model=WorkspaceConfigRead)
def get_provider_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "provider")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_nanobot_provider_config(workspace, settings)


@router.get("/{workspace_id}/agent-config", response_model=WorkspaceConfigRead)
def get_agent_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "agent")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_nanobot_agent_config(workspace, settings)


@router.put("/{workspace_id}/agent-config", response_model=WorkspaceConfigRead)
def put_agent_config_api(
    workspace_id: int,
    payload: WorkspaceConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "agent")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    source_config_path = local_path / ".nanobot" / "config.json"
    try:
        base_config = config_renderer.load_nanobot_instance_config(source_config_path)
        updated_config = config_renderer.merge_agent_defaults_config(base_config, payload.values)
        config_renderer.validate_agent_defaults_config(updated_config)
        config_renderer.write_nanobot_config(source_config_path, updated_config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    mark_workspace_runtime_for_restart(db, workspace)
    db.commit()
    render_workspace_artifacts(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_nanobot_agent_config(workspace, settings)


@router.put("/{workspace_id}/provider-config", response_model=WorkspaceConfigRead)
def put_provider_config_api(
    workspace_id: int,
    payload: WorkspaceConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "provider")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    source_config_path = local_path / ".nanobot" / "config.json"
    try:
        base_config = config_renderer.load_nanobot_instance_config(source_config_path)
        updated_config = config_renderer.merge_provider_config(base_config, payload.values)
        config_renderer.validate_provider_config(updated_config)
        config_renderer.write_nanobot_config(source_config_path, updated_config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    mark_workspace_runtime_for_restart(db, workspace)
    db.commit()
    render_workspace_artifacts(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_nanobot_provider_config(workspace, settings)


@router.get("/{workspace_id}/gateway-config", response_model=WorkspaceConfigRead)
def get_gateway_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="gateway.yaml mode has been removed; use the Nanobot native activation model instead",
    )


@router.put("/{workspace_id}/gateway-config", response_model=WorkspaceConfigRead)
def put_gateway_config_api(
    workspace_id: int,
    payload: WorkspaceConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="gateway.yaml mode has been removed; use the Nanobot native activation model instead",
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
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
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
    openclaw_manager.reload_if_running(db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_openclaw_config(workspace, settings)


@router.get("/{workspace_id}/openclaw-channel-config", response_model=WorkspaceConfigRead)
def get_openclaw_channel_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_openclaw_channel_config(workspace, settings)


@router.get("/{workspace_id}/runtime", response_model=RuntimeStatusResponse)
def get_workspace_runtime_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        return serialize_runtime_status(gateway_manager.status(db, workspace))
    return serialize_openclaw_route_runtime(workspace)


@router.post("/{workspace_id}/runtime/start", response_model=RuntimeStatusResponse)
def start_workspace_runtime_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "runtime")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    render_workspace_artifacts(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_runtime_status(gateway_manager.start(db, workspace))


@router.post("/{workspace_id}/runtime/stop", response_model=RuntimeStatusResponse)
def stop_workspace_runtime_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "runtime")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_runtime_status(gateway_manager.stop(db, workspace))


@router.post("/{workspace_id}/runtime/restart", response_model=RuntimeStatusResponse)
def restart_workspace_runtime_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "runtime")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    render_workspace_artifacts(db, workspace, settings)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_runtime_status(gateway_manager.restart(db, workspace))


@router.put("/{workspace_id}/openclaw-channel-config", response_model=WorkspaceConfigRead)
def put_openclaw_channel_config_api(
    workspace_id: int,
    payload: OpenClawChannelConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> WorkspaceConfigRead:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    try:
        merged_channel = config_renderer.merge_openclaw_channel_config(
            workspace.config.openclaw_channel_json,
            payload.values,
        )
        merged_channel = config_renderer.validate_openclaw_channel_config(merged_channel)
        merged_binding = config_renderer.merge_openclaw_binding_config(
            workspace.config.openclaw_binding_json,
            {"enabled": merged_channel["enabled"]},
        )
        merged_binding = config_renderer.validate_openclaw_binding_config(merged_binding)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    workspace.config.openclaw_channel_json = merged_channel
    workspace.config.openclaw_binding_json = merged_binding
    db.add(workspace.config)
    db.commit()
    render_workspace_artifacts(db, workspace, settings)
    openclaw_manager.reload_if_running(db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_openclaw_channel_config(workspace, settings)


@router.get("/admin/all", response_model=list[WorkspaceRead], include_in_schema=False)
def list_all_workspaces_admin(
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceRead]:
    workspaces = db.scalars(select(models.Workspace).order_by(models.Workspace.created_at.desc())).all()
    return [WorkspaceRead.model_validate(workspace) for workspace in workspaces]
