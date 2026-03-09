from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import docker
from docker.errors import APIError, DockerException, NotFound
from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.constants import (
    GATEWAY_STATE_ERROR,
    GATEWAY_STATE_RUNNING,
    GATEWAY_STATE_STARTING,
    GATEWAY_STATE_STOPPED,
    GATEWAY_STATE_STOPPING,
)


@dataclass
class GatewayRuntimeState:
    state: str
    container_name: str
    container_id: str | None = None
    last_error: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None


class GatewayManager:
    def sync_managed_containers(self, db: Session) -> None:
        raise NotImplementedError

    def start(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        raise NotImplementedError

    def stop(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        raise NotImplementedError

    def restart(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        raise NotImplementedError

    def status(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        raise NotImplementedError


class NullGatewayManager(GatewayManager):
    def sync_managed_containers(self, db: Session) -> None:
        return None

    def start(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        instance = workspace.gateway_instance
        instance.state = GATEWAY_STATE_ERROR
        instance.last_error = "docker is not available"
        db.add(instance)
        db.commit()
        return GatewayRuntimeState(state=instance.state, container_name=instance.container_name, last_error=instance.last_error)

    def stop(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        instance = workspace.gateway_instance
        instance.state = GATEWAY_STATE_STOPPED
        db.add(instance)
        db.commit()
        return GatewayRuntimeState(state=instance.state, container_name=instance.container_name, last_error=instance.last_error)

    def restart(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        return self.start(db, workspace)

    def status(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        instance = workspace.gateway_instance
        return GatewayRuntimeState(
            state=instance.state,
            container_name=instance.container_name,
            container_id=instance.last_container_id,
            last_error=instance.last_error,
            started_at=instance.started_at,
            stopped_at=instance.stopped_at,
        )


class DockerGatewayManager(GatewayManager):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = docker.from_env()

    def container_name(self, workspace_id: int) -> str:
        return f"claw-gateway-{workspace_id}"

    def _host_path(self, workspace: models.Workspace) -> str:
        return workspace.host_path

    def _labels(self, workspace: models.Workspace) -> dict[str, str]:
        return {
            "claw.managed": "true",
            "claw.workspace_id": str(workspace.id),
            "claw.owner_user_id": str(workspace.owner_user_id),
        }

    def _save_state(self, db: Session, workspace: models.Workspace, runtime: GatewayRuntimeState) -> GatewayRuntimeState:
        instance = workspace.gateway_instance
        instance.container_name = runtime.container_name
        instance.image = self.settings.gateway_image
        instance.state = runtime.state
        instance.last_container_id = runtime.container_id
        instance.last_error = runtime.last_error
        instance.started_at = runtime.started_at
        instance.stopped_at = runtime.stopped_at
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return runtime

    def _map_container_state(self, container: Any) -> GatewayRuntimeState:
        raw_status = getattr(container, "status", None) or container.attrs.get("State", {}).get("Status", "exited")
        state = {
            "created": GATEWAY_STATE_STARTING,
            "restarting": GATEWAY_STATE_STARTING,
            "running": GATEWAY_STATE_RUNNING,
            "exited": GATEWAY_STATE_STOPPED,
            "dead": GATEWAY_STATE_ERROR,
            "removing": GATEWAY_STATE_STOPPING,
            "paused": GATEWAY_STATE_STOPPING,
        }.get(raw_status, GATEWAY_STATE_ERROR)
        started_at = self._parse_container_time(container.attrs.get("State", {}).get("StartedAt"))
        finished_at = self._parse_container_time(container.attrs.get("State", {}).get("FinishedAt"))
        error = container.attrs.get("State", {}).get("Error") or None
        return GatewayRuntimeState(
            state=state,
            container_name=container.name,
            container_id=container.id,
            last_error=error,
            started_at=started_at,
            stopped_at=finished_at if state != GATEWAY_STATE_RUNNING else None,
        )

    def _parse_container_time(self, value: str | None) -> datetime | None:
        if not value or value.startswith("0001-01-01"):
            return None
        cleaned = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None

    def _get_or_create_container(self, workspace: models.Workspace):
        name = workspace.gateway_instance.container_name
        try:
            return self.client.containers.get(name)
        except NotFound:
            return self.client.containers.create(
                image=self.settings.gateway_image,
                name=name,
                detach=True,
                labels=self._labels(workspace),
                environment={
                    "NANOBOT_CONFIG_PATH": self.settings.nanobot_config_path,
                    "GATEWAY_CONFIG_PATH": self.settings.gateway_config_path,
                    "WORKSPACE_ID": str(workspace.id),
                    "WORKSPACE_NAME": workspace.name,
                },
                volumes={
                    self._host_path(workspace): {
                        "bind": self.settings.gateway_workspace_mount,
                        "mode": "rw",
                    }
                },
            )

    def sync_managed_containers(self, db: Session) -> None:
        containers = self.client.containers.list(all=True, filters={"label": "claw.managed=true"})
        workspace_map = {workspace.id: workspace for workspace in db.query(models.Workspace).all()}
        for container in containers:
            workspace_id = container.labels.get("claw.workspace_id")
            if not workspace_id:
                continue
            workspace = workspace_map.get(int(workspace_id))
            if not workspace or not workspace.gateway_instance:
                continue
            runtime = self._map_container_state(container)
            self._save_state(db, workspace, runtime)

    def start(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        try:
            container = self._get_or_create_container(workspace)
            if container.status != "running":
                container.start()
            container.reload()
            runtime = self._map_container_state(container)
            if runtime.started_at is None:
                runtime.started_at = datetime.now(timezone.utc)
            return self._save_state(db, workspace, runtime)
        except (APIError, DockerException) as exc:
            runtime = GatewayRuntimeState(
                state=GATEWAY_STATE_ERROR,
                container_name=workspace.gateway_instance.container_name,
                last_error=str(exc),
                container_id=workspace.gateway_instance.last_container_id,
            )
            return self._save_state(db, workspace, runtime)

    def stop(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        name = workspace.gateway_instance.container_name
        try:
            container = self.client.containers.get(name)
            if container.status == "running":
                container.stop(timeout=self.settings.gateway_stop_timeout)
            container.reload()
            runtime = self._map_container_state(container)
            if runtime.stopped_at is None:
                runtime.stopped_at = datetime.now(timezone.utc)
            return self._save_state(db, workspace, runtime)
        except NotFound:
            runtime = GatewayRuntimeState(
                state=GATEWAY_STATE_STOPPED,
                container_name=name,
                container_id=None,
                stopped_at=datetime.now(timezone.utc),
            )
            return self._save_state(db, workspace, runtime)
        except (APIError, DockerException) as exc:
            runtime = GatewayRuntimeState(
                state=GATEWAY_STATE_ERROR,
                container_name=name,
                container_id=workspace.gateway_instance.last_container_id,
                last_error=str(exc),
            )
            return self._save_state(db, workspace, runtime)

    def restart(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        try:
            container = self._get_or_create_container(workspace)
            if container.status != "running":
                container.start()
            else:
                container.restart(timeout=self.settings.gateway_stop_timeout)
            container.reload()
            runtime = self._map_container_state(container)
            if runtime.started_at is None:
                runtime.started_at = datetime.now(timezone.utc)
            return self._save_state(db, workspace, runtime)
        except (APIError, DockerException) as exc:
            runtime = GatewayRuntimeState(
                state=GATEWAY_STATE_ERROR,
                container_name=workspace.gateway_instance.container_name,
                container_id=workspace.gateway_instance.last_container_id,
                last_error=str(exc),
            )
            return self._save_state(db, workspace, runtime)

    def status(self, db: Session, workspace: models.Workspace) -> GatewayRuntimeState:
        name = workspace.gateway_instance.container_name
        try:
            container = self.client.containers.get(name)
            runtime = self._map_container_state(container)
            return self._save_state(db, workspace, runtime)
        except NotFound:
            runtime = GatewayRuntimeState(
                state=GATEWAY_STATE_STOPPED,
                container_name=name,
                container_id=None,
                last_error=None,
                started_at=workspace.gateway_instance.started_at,
                stopped_at=workspace.gateway_instance.stopped_at,
            )
            return self._save_state(db, workspace, runtime)
        except (APIError, DockerException) as exc:
            runtime = GatewayRuntimeState(
                state=GATEWAY_STATE_ERROR,
                container_name=name,
                container_id=workspace.gateway_instance.last_container_id,
                last_error=str(exc),
                started_at=workspace.gateway_instance.started_at,
                stopped_at=workspace.gateway_instance.stopped_at,
            )
            return self._save_state(db, workspace, runtime)


def build_gateway_manager(settings: Settings) -> GatewayManager:
    try:
        return DockerGatewayManager(settings)
    except DockerException:
        return NullGatewayManager()
