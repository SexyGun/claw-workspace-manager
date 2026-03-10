from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.constants import (
    RUNTIME_KIND_OPENCLAW,
    RUNTIME_SCOPE_ROUTE,
    RUNTIME_STATE_CONFIGURED,
    RUNTIME_STATE_INACTIVE,
    WORKSPACE_TYPE_BASE,
    WORKSPACE_TYPE_OPENCLAW,
)
from app.schemas import (
    OpenClawConfigRead,
    OpenClawRouteRead,
    RuntimeStatusResponse,
    WorkspaceConfigRead,
    WorkspaceRead,
    WorkspaceSummary,
)
from app.services import config_renderer, workspace as workspace_service
from app.services.gateway import GatewayManager
from app.services.openclaw_runtime import OpenClawRuntimeManager
from app.services.runtime_control import RuntimeStatus


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


def workspace_activation_state(workspace: models.Workspace) -> str | None:
    if workspace.workspace_type == WORKSPACE_TYPE_BASE:
        runtime = workspace.runtime
        if runtime is None:
            return None
        if runtime.state == "error":
            return "error"
        if runtime.state in {"running", "starting", "stopping"}:
            return "active"
        return "inactive"

    if workspace.workspace_type == WORKSPACE_TYPE_OPENCLAW:
        route = config_renderer.build_openclaw_route(
            workspace.config.openclaw_channel_json or config_renderer.default_openclaw_channel_config(),
            workspace.config.openclaw_binding_json or config_renderer.default_openclaw_binding_config(),
            workspace.id,
        )
        return "active" if route["enabled"] else "inactive"

    return None


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
            "activation_state": workspace_activation_state(workspace),
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
        raw_json5=config_renderer.openclaw_raw_json(config_renderer.mask_openclaw_config(openclaw_values)),
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


def build_workspace_summary(
    db: Session,
    workspace: models.Workspace,
    settings: Settings,
    gateway_manager: GatewayManager,
    openclaw_manager: OpenClawRuntimeManager,
) -> WorkspaceSummary:
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
