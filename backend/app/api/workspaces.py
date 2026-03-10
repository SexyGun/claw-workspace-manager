from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.api.workspace_serializers import (
    build_workspace_summary,
    serialize_nanobot_agent_config,
    serialize_nanobot_config,
    serialize_nanobot_provider_config,
    serialize_openclaw_channel_config,
    serialize_openclaw_config,
    serialize_openclaw_route_runtime,
    serialize_runtime_status,
    serialize_workspace,
    serialize_workspace_list_item,
    workspace_activation_state,
)
from app.config import Settings
from app.constants import SHARED_RUNTIME_KEY_OPENCLAW, WORKSPACE_TYPE_BASE, WORKSPACE_TYPE_OPENCLAW
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
    DiagnosticLogEntryRead,
    MessageResponse,
    OpenClawChannelConfigPayload,
    OpenClawConfigPayload,
    OpenClawConfigRead,
    RuntimeStatusResponse,
    WorkspaceDiagnosticChecksRead,
    WorkspaceDiagnosticLogsRead,
    WorkspaceConfigPayload,
    WorkspaceConfigRead,
    WorkspaceCreate,
    WorkspaceListItemRead,
    WorkspaceRead,
    WorkspaceSetupConfigPayload,
    WorkspaceSummary,
    WorkspaceTypeRead,
    WorkspaceUpdate,
)
from app.services import config_renderer, workspace as workspace_service
from app.services.gateway import GatewayManager
from app.services.openclaw_runtime import OpenClawRuntimeManager
from app.services.workspace_dashboard import build_diagnostic_checks, build_diagnostic_logs
from app.services.workspace_artifacts import (
    ensure_workspace_type,
    load_workspace,
    mark_workspace_runtime_for_restart,
    render_openclaw_service_artifacts,
    render_workspace_artifacts,
)
from app.services.workspace_profiles import get_workspace_profiles

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
workspace_type_router = APIRouter(tags=["workspaces"])


def load_owned_workspace(workspace_id: int, current_user: models.User, db: Session) -> models.Workspace:
    workspace = get_workspace_for_user(workspace_id, current_user, db)
    loaded = load_workspace(db, workspace.id)
    assert loaded is not None
    return loaded


@workspace_type_router.get("/workspace-types", response_model=list[WorkspaceTypeRead])
def list_workspace_types(settings: Settings = Depends(get_app_settings)) -> list[WorkspaceTypeRead]:
    profiles = get_workspace_profiles(settings).values()
    return [WorkspaceTypeRead(key=profile.key, label=profile.label, description=profile.description) for profile in profiles]


@router.get("", response_model=list[WorkspaceListItemRead])
def list_workspaces(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> list[WorkspaceListItemRead]:
    query = (
        select(models.Workspace)
        .options(selectinload(models.Workspace.runtime), selectinload(models.Workspace.config))
        .order_by(models.Workspace.created_at.desc())
    )
    if current_user.role != "admin":
        query = query.where(models.Workspace.owner_user_id == current_user.id)
    workspaces = db.scalars(query).all()
    shared_runtime = db.get(models.SharedRuntime, SHARED_RUNTIME_KEY_OPENCLAW)
    return [
        serialize_workspace_list_item(workspace, settings, shared_runtime=shared_runtime)
        for workspace in workspaces
    ]


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
    workspace = load_owned_workspace(workspace_id, current_user, db)
    return build_workspace_summary(db, workspace, settings, gateway_manager, openclaw_manager)


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


@router.delete("/{workspace_id}", response_model=MessageResponse)
def delete_workspace_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> MessageResponse:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    workspace_type = workspace.workspace_type
    if workspace_type == WORKSPACE_TYPE_BASE and workspace.runtime is not None:
        gateway_manager.stop(db, workspace)
    workspace_service.delete_workspace(db, settings, workspace)
    if workspace_type == WORKSPACE_TYPE_OPENCLAW:
        render_openclaw_service_artifacts(db, settings)
        openclaw_manager.reload_if_running(db)
    return MessageResponse(message="Workspace deleted")


@router.get("/{workspace_id}/nanobot-config", response_model=WorkspaceConfigRead)
def get_nanobot_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "nanobot")
    return serialize_nanobot_config(workspace, settings)


@router.put("/{workspace_id}/setup-config", response_model=WorkspaceSummary)
def put_workspace_setup_config_api(
    workspace_id: int,
    payload: WorkspaceSetupConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> WorkspaceSummary:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
        source_config_path = local_path / ".nanobot" / "config.json"
        updated_config = config_renderer.load_nanobot_instance_config(source_config_path)
        try:
            if payload.nanobot:
                merged_channel = config_renderer.merge_channel_config(workspace.config.channel_config_json, payload.nanobot)
                config_renderer.validate_channel_config(merged_channel)
                workspace.config.channel_config_json = merged_channel
            if payload.agent:
                updated_config = config_renderer.merge_agent_defaults_config(updated_config, payload.agent)
                config_renderer.validate_agent_defaults_config(updated_config)
            if payload.provider:
                updated_config = config_renderer.merge_provider_config(updated_config, payload.provider)
                config_renderer.validate_provider_config(updated_config)
            config_renderer.write_nanobot_config(source_config_path, updated_config)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        mark_workspace_runtime_for_restart(db, workspace)
        db.add(workspace.config)
        db.commit()
        render_workspace_artifacts(db, workspace, settings)
        workspace = load_workspace(db, workspace.id)
        assert workspace is not None
        if payload.start_after_save:
            gateway_manager.start(db, workspace)
            workspace = load_workspace(db, workspace.id)
            assert workspace is not None
        return build_workspace_summary(db, workspace, settings, gateway_manager, openclaw_manager)

    try:
        base_config = workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
        if payload.openclaw_raw_json5 and payload.openclaw_raw_json5.strip():
            base_config = config_renderer.restore_masked_openclaw_config(
                base_config,
                config_renderer.parse_openclaw_raw_json5(payload.openclaw_raw_json5),
            )
        if payload.openclaw:
            base_config = config_renderer.merge_openclaw_structured_values(base_config, payload.openclaw)
        merged_openclaw = config_renderer.validate_openclaw_config(base_config)
        merged_channel = config_renderer.merge_openclaw_channel_config(
            workspace.config.openclaw_channel_json,
            payload.openclaw_channel,
        )
        merged_channel = config_renderer.validate_openclaw_channel_config(merged_channel)
        binding_updates: dict[str, object] = {}
        if not merged_channel["enabled"]:
            binding_updates["enabled"] = False
        if payload.start_after_save:
            binding_updates["enabled"] = True
        merged_binding = config_renderer.merge_openclaw_binding_config(
            workspace.config.openclaw_binding_json,
            binding_updates,
        )
        merged_binding = config_renderer.validate_openclaw_binding_config(merged_binding)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    workspace.config.openclaw_config_json = merged_openclaw
    workspace.config.openclaw_channel_json = merged_channel
    workspace.config.openclaw_binding_json = merged_binding
    db.add(workspace.config)
    db.commit()
    render_workspace_artifacts(db, workspace, settings)
    openclaw_manager.reload_if_running(db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return build_workspace_summary(db, workspace, settings, gateway_manager, openclaw_manager)


@router.put("/{workspace_id}/nanobot-config", response_model=WorkspaceConfigRead)
def put_nanobot_config_api(
    workspace_id: int,
    payload: WorkspaceConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "nanobot")
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
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "provider")
    return serialize_nanobot_provider_config(workspace, settings)


@router.get("/{workspace_id}/agent-config", response_model=WorkspaceConfigRead)
def get_agent_config_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "agent")
    return serialize_nanobot_agent_config(workspace, settings)


@router.put("/{workspace_id}/agent-config", response_model=WorkspaceConfigRead)
def put_agent_config_api(
    workspace_id: int,
    payload: WorkspaceConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> WorkspaceConfigRead:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "agent")
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
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_BASE, "provider")
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
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
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
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    try:
        base_config = workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
        if payload.raw_json5 and payload.raw_json5.strip():
            base_config = config_renderer.restore_masked_openclaw_config(
                base_config,
                config_renderer.parse_openclaw_raw_json5(payload.raw_json5),
            )
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
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    return serialize_openclaw_channel_config(workspace, settings)


@router.get("/{workspace_id}/runtime", response_model=RuntimeStatusResponse)
def get_workspace_runtime_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
) -> RuntimeStatusResponse:
    workspace = load_owned_workspace(workspace_id, current_user, db)
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
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        render_workspace_artifacts(db, workspace, settings)
        workspace = load_workspace(db, workspace.id)
        assert workspace is not None
        return serialize_runtime_status(gateway_manager.start(db, workspace))

    binding = config_renderer.merge_openclaw_binding_config(workspace.config.openclaw_binding_json, {"enabled": True})
    workspace.config.openclaw_binding_json = config_renderer.validate_openclaw_binding_config(binding)
    db.add(workspace.config)
    db.commit()
    render_workspace_artifacts(db, workspace, settings)
    openclaw_manager.reload_if_running(db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_openclaw_route_runtime(workspace)


@router.post("/{workspace_id}/runtime/stop", response_model=RuntimeStatusResponse)
def stop_workspace_runtime_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        return serialize_runtime_status(gateway_manager.stop(db, workspace))

    binding = config_renderer.merge_openclaw_binding_config(workspace.config.openclaw_binding_json, {"enabled": False})
    workspace.config.openclaw_binding_json = config_renderer.validate_openclaw_binding_config(binding)
    db.add(workspace.config)
    db.commit()
    render_workspace_artifacts(db, workspace, settings)
    openclaw_manager.reload_if_running(db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_openclaw_route_runtime(workspace)


@router.post("/{workspace_id}/runtime/restart", response_model=RuntimeStatusResponse)
def restart_workspace_runtime_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        render_workspace_artifacts(db, workspace, settings)
        workspace = load_workspace(db, workspace.id)
        assert workspace is not None
        return serialize_runtime_status(gateway_manager.restart(db, workspace))

    render_workspace_artifacts(db, workspace, settings)
    openclaw_manager.reload_if_running(db)
    workspace = load_workspace(db, workspace.id)
    assert workspace is not None
    return serialize_openclaw_route_runtime(workspace)


@router.put("/{workspace_id}/openclaw-channel-config", response_model=WorkspaceConfigRead)
def put_openclaw_channel_config_api(
    workspace_id: int,
    payload: OpenClawChannelConfigPayload,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> WorkspaceConfigRead:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    ensure_workspace_type(workspace, WORKSPACE_TYPE_OPENCLAW, "openclaw")
    try:
        merged_channel = config_renderer.merge_openclaw_channel_config(
            workspace.config.openclaw_channel_json,
            payload.values,
        )
        merged_channel = config_renderer.validate_openclaw_channel_config(merged_channel)
        binding_updates = {"enabled": False} if not merged_channel["enabled"] else {}
        merged_binding = config_renderer.merge_openclaw_binding_config(workspace.config.openclaw_binding_json, binding_updates)
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


@router.post("/{workspace_id}/diagnostics/checks", response_model=WorkspaceDiagnosticChecksRead)
def workspace_diagnostic_checks_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> WorkspaceDiagnosticChecksRead:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    runtime_status = gateway_manager.status(db, workspace) if workspace.workspace_type == WORKSPACE_TYPE_BASE else None
    shared_runtime_status = openclaw_manager.service_status(db) if workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW else None
    checks = build_diagnostic_checks(
        workspace,
        settings,
        workspace_activation_state(workspace),
        runtime=runtime_status or workspace.runtime,
        shared_runtime=shared_runtime_status,
    )
    return WorkspaceDiagnosticChecksRead(
        checked_at=datetime.now(timezone.utc),
        checks=checks,
    )


@router.get("/{workspace_id}/diagnostics/logs", response_model=WorkspaceDiagnosticLogsRead)
def workspace_diagnostic_logs_api(
    workspace_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    gateway_manager: GatewayManager = Depends(get_gateway_manager),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
    limit: int = 50,
) -> WorkspaceDiagnosticLogsRead:
    workspace = load_owned_workspace(workspace_id, current_user, db)
    runtime_status = gateway_manager.status(db, workspace) if workspace.workspace_type == WORKSPACE_TYPE_BASE else None
    shared_runtime_status = openclaw_manager.service_status(db) if workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW else None
    logs = build_diagnostic_logs(
        workspace,
        settings,
        workspace_activation_state(workspace),
        runtime=runtime_status or workspace.runtime,
        shared_runtime=shared_runtime_status,
        limit=max(1, min(limit, 200)),
    )
    return WorkspaceDiagnosticLogsRead(
        source=logs["source"],
        unit_name=logs["unit_name"],
        entries=[DiagnosticLogEntryRead.model_validate(entry) for entry in logs["entries"]],
    )


@router.get("/admin/all", response_model=list[WorkspaceListItemRead], include_in_schema=False)
def list_all_workspaces_admin(
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> list[WorkspaceListItemRead]:
    workspaces = db.scalars(
        select(models.Workspace)
        .options(selectinload(models.Workspace.runtime), selectinload(models.Workspace.config))
        .order_by(models.Workspace.created_at.desc())
    ).all()
    shared_runtime = db.get(models.SharedRuntime, SHARED_RUNTIME_KEY_OPENCLAW)
    return [
        serialize_workspace_list_item(workspace, settings, shared_runtime=shared_runtime)
        for workspace in workspaces
    ]
