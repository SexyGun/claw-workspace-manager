from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

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
class OpenClawRuntimeState:
    state: str
    container_name: str
    container_id: Optional[str] = None
    last_error: Optional[str] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None


class OpenClawRuntimeManager:
    def sync_managed_containers(self, db: Session) -> None:
        raise NotImplementedError

    def start(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        raise NotImplementedError

    def stop(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        raise NotImplementedError

    def restart(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        raise NotImplementedError

    def status(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        raise NotImplementedError


class NullOpenClawRuntimeManager(OpenClawRuntimeManager):
    def sync_managed_containers(self, db: Session) -> None:
        return None

    def start(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        instance = workspace.openclaw_instance
        assert instance is not None
        instance.state = GATEWAY_STATE_ERROR
        instance.last_error = "docker is not available"
        db.add(instance)
        db.commit()
        return OpenClawRuntimeState(state=instance.state, container_name=instance.container_name, last_error=instance.last_error)

    def stop(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        instance = workspace.openclaw_instance
        assert instance is not None
        instance.state = GATEWAY_STATE_STOPPED
        db.add(instance)
        db.commit()
        return OpenClawRuntimeState(state=instance.state, container_name=instance.container_name, last_error=instance.last_error)

    def restart(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        return self.start(db, workspace)

    def status(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        instance = workspace.openclaw_instance
        assert instance is not None
        return OpenClawRuntimeState(
            state=instance.state,
            container_name=instance.container_name,
            container_id=instance.last_container_id,
            last_error=instance.last_error,
            started_at=instance.started_at,
            stopped_at=instance.stopped_at,
        )


class DockerOpenClawRuntimeManager(OpenClawRuntimeManager):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = docker.from_env()

    def _labels(self, workspace: models.Workspace) -> dict[str, str]:
        return {
            "claw.managed": "true",
            "claw.runtime": "openclaw",
            "claw.workspace_id": str(workspace.id),
            "claw.owner_user_id": str(workspace.owner_user_id),
        }

    def _save_state(self, db: Session, workspace: models.Workspace, runtime: OpenClawRuntimeState) -> OpenClawRuntimeState:
        instance = workspace.openclaw_instance
        assert instance is not None
        instance.container_name = runtime.container_name
        instance.image = self.settings.openclaw_image
        instance.state = runtime.state
        instance.last_container_id = runtime.container_id
        instance.last_error = runtime.last_error
        instance.started_at = runtime.started_at
        instance.stopped_at = runtime.stopped_at
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return runtime

    def _parse_container_time(self, value: Optional[str]) -> Optional[datetime]:
        if not value or value.startswith("0001-01-01"):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _map_container_state(self, container: Any) -> OpenClawRuntimeState:
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
        return OpenClawRuntimeState(
            state=state,
            container_name=container.name,
            container_id=container.id,
            last_error=container.attrs.get("State", {}).get("Error") or None,
            started_at=self._parse_container_time(container.attrs.get("State", {}).get("StartedAt")),
            stopped_at=self._parse_container_time(container.attrs.get("State", {}).get("FinishedAt"))
            if state != GATEWAY_STATE_RUNNING
            else None,
        )

    def _get_or_create_container(self, workspace: models.Workspace):
        instance = workspace.openclaw_instance
        assert instance is not None
        name = instance.container_name
        try:
            return self.client.containers.get(name)
        except NotFound:
            return self.client.containers.create(
                image=self.settings.openclaw_image,
                name=name,
                detach=True,
                labels=self._labels(workspace),
                working_dir=f"{self.settings.openclaw_workspace_mount}/.openclaw/workspace",
                environment={
                    "HOME": self.settings.openclaw_workspace_mount,
                    "WORKSPACE_ID": str(workspace.id),
                    "WORKSPACE_NAME": workspace.name,
                },
                volumes={
                    workspace.host_path: {
                        "bind": self.settings.openclaw_workspace_mount,
                        "mode": "rw",
                    }
                },
            )

    def sync_managed_containers(self, db: Session) -> None:
        containers = self.client.containers.list(all=True, filters={"label": ["claw.managed=true", "claw.runtime=openclaw"]})
        workspace_map = {workspace.id: workspace for workspace in db.query(models.Workspace).all()}
        for container in containers:
            workspace_id = container.labels.get("claw.workspace_id")
            if not workspace_id:
                continue
            workspace = workspace_map.get(int(workspace_id))
            if not workspace or not workspace.openclaw_instance:
                continue
            self._save_state(db, workspace, self._map_container_state(container))

    def start(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
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
            return self._save_state(
                db,
                workspace,
                OpenClawRuntimeState(
                    state=GATEWAY_STATE_ERROR,
                    container_name=workspace.openclaw_instance.container_name,  # type: ignore[union-attr]
                    container_id=workspace.openclaw_instance.last_container_id,  # type: ignore[union-attr]
                    last_error=str(exc),
                ),
            )

    def stop(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        instance = workspace.openclaw_instance
        assert instance is not None
        try:
            container = self.client.containers.get(instance.container_name)
            if container.status == "running":
                container.stop(timeout=self.settings.gateway_stop_timeout)
            container.reload()
            runtime = self._map_container_state(container)
            if runtime.stopped_at is None:
                runtime.stopped_at = datetime.now(timezone.utc)
            return self._save_state(db, workspace, runtime)
        except NotFound:
            return self._save_state(
                db,
                workspace,
                OpenClawRuntimeState(
                    state=GATEWAY_STATE_STOPPED,
                    container_name=instance.container_name,
                    stopped_at=datetime.now(timezone.utc),
                ),
            )
        except (APIError, DockerException) as exc:
            return self._save_state(
                db,
                workspace,
                OpenClawRuntimeState(
                    state=GATEWAY_STATE_ERROR,
                    container_name=instance.container_name,
                    container_id=instance.last_container_id,
                    last_error=str(exc),
                ),
            )

    def restart(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
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
            instance = workspace.openclaw_instance
            assert instance is not None
            return self._save_state(
                db,
                workspace,
                OpenClawRuntimeState(
                    state=GATEWAY_STATE_ERROR,
                    container_name=instance.container_name,
                    container_id=instance.last_container_id,
                    last_error=str(exc),
                ),
            )

    def status(self, db: Session, workspace: models.Workspace) -> OpenClawRuntimeState:
        instance = workspace.openclaw_instance
        assert instance is not None
        try:
            container = self.client.containers.get(instance.container_name)
            return self._save_state(db, workspace, self._map_container_state(container))
        except NotFound:
            return self._save_state(
                db,
                workspace,
                OpenClawRuntimeState(
                    state=GATEWAY_STATE_STOPPED,
                    container_name=instance.container_name,
                    started_at=instance.started_at,
                    stopped_at=instance.stopped_at,
                ),
            )
        except (APIError, DockerException) as exc:
            return self._save_state(
                db,
                workspace,
                OpenClawRuntimeState(
                    state=GATEWAY_STATE_ERROR,
                    container_name=instance.container_name,
                    container_id=instance.last_container_id,
                    last_error=str(exc),
                    started_at=instance.started_at,
                    stopped_at=instance.stopped_at,
                ),
            )


def build_openclaw_runtime_manager(settings: Settings) -> OpenClawRuntimeManager:
    try:
        return DockerOpenClawRuntimeManager(settings)
    except DockerException:
        return NullOpenClawRuntimeManager()
