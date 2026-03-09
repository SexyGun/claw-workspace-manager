from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.constants import (
    RUNTIME_CONTROLLER_SYSTEMD,
    RUNTIME_KIND_NANOBOT,
    RUNTIME_SCOPE_WORKSPACE,
    RUNTIME_STATE_ERROR,
    RUNTIME_STATE_STOPPED,
)
from app.services.runtime_control import (
    NullController,
    RuntimeControlError,
    RuntimeStatus,
    SystemdController,
    SystemdUnitStatus,
    build_systemd_controller,
)


class GatewayManager:
    def sync_managed_containers(self, db: Session) -> None:
        raise NotImplementedError

    def start(self, db: Session, workspace: models.Workspace) -> RuntimeStatus:
        raise NotImplementedError

    def stop(self, db: Session, workspace: models.Workspace) -> RuntimeStatus:
        raise NotImplementedError

    def restart(self, db: Session, workspace: models.Workspace) -> RuntimeStatus:
        raise NotImplementedError

    def status(self, db: Session, workspace: models.Workspace) -> RuntimeStatus:
        raise NotImplementedError


class NativeGatewayManager(GatewayManager):
    def __init__(self, settings: Settings, controller: SystemdController | NullController):
        self.settings = settings
        self.controller = controller

    def sync_managed_containers(self, db: Session) -> None:
        runtimes = db.query(models.WorkspaceRuntime).all()
        for runtime in runtimes:
            if runtime.runtime_kind != RUNTIME_KIND_NANOBOT:
                continue
            workspace = db.get(models.Workspace, runtime.workspace_id)
            if workspace is None:
                continue
            self.status(db, workspace)

    def start(self, db: Session, workspace: models.Workspace) -> RuntimeStatus:
        runtime = self._require_runtime(workspace)
        try:
            unit_status = self.controller.start(runtime.unit_name)
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            return self._save_error(db, runtime, str(exc))

    def stop(self, db: Session, workspace: models.Workspace) -> RuntimeStatus:
        runtime = self._require_runtime(workspace)
        try:
            unit_status = self.controller.stop(runtime.unit_name)
            if unit_status.stopped_at is None:
                unit_status.stopped_at = datetime.now(timezone.utc)
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            return self._save_error(db, runtime, str(exc))

    def restart(self, db: Session, workspace: models.Workspace) -> RuntimeStatus:
        runtime = self._require_runtime(workspace)
        try:
            unit_status = self.controller.restart(runtime.unit_name)
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            return self._save_error(db, runtime, str(exc))

    def status(self, db: Session, workspace: models.Workspace) -> RuntimeStatus:
        runtime = self._require_runtime(workspace)
        try:
            unit_status = self.controller.status(runtime.unit_name)
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            return self._save_error(db, runtime, str(exc))

    def _require_runtime(self, workspace: models.Workspace) -> models.WorkspaceRuntime:
        runtime = workspace.runtime
        if runtime is None:
            raise ValueError("workspace runtime is not configured")
        return runtime

    def _save_status(
        self,
        db: Session,
        runtime: models.WorkspaceRuntime,
        unit_status: SystemdUnitStatus,
    ) -> RuntimeStatus:
        runtime.controller_kind = RUNTIME_CONTROLLER_SYSTEMD
        runtime.unit_name = unit_status.unit_name
        runtime.process_id = unit_status.process_id
        runtime.state = unit_status.state
        runtime.last_error = None
        runtime.started_at = unit_status.started_at
        runtime.stopped_at = unit_status.stopped_at if unit_status.state != "running" else None
        runtime.needs_restart = False
        db.add(runtime)
        db.commit()
        db.refresh(runtime)
        return RuntimeStatus(
            state=runtime.state,
            scope=runtime.scope,
            controller_kind=runtime.controller_kind,
            unit_name=runtime.unit_name,
            process_id=runtime.process_id,
            listen_port=runtime.listen_port,
            last_error=runtime.last_error,
            started_at=runtime.started_at,
            stopped_at=runtime.stopped_at,
            needs_restart=runtime.needs_restart,
        )

    def _save_error(self, db: Session, runtime: models.WorkspaceRuntime, error: str) -> RuntimeStatus:
        runtime.state = RUNTIME_STATE_ERROR if not isinstance(self.controller, NullController) else RUNTIME_STATE_STOPPED
        runtime.last_error = error
        db.add(runtime)
        db.commit()
        db.refresh(runtime)
        return RuntimeStatus(
            state=runtime.state,
            scope=runtime.scope,
            controller_kind=runtime.controller_kind,
            unit_name=runtime.unit_name,
            process_id=runtime.process_id,
            listen_port=runtime.listen_port,
            last_error=runtime.last_error,
            started_at=runtime.started_at,
            stopped_at=runtime.stopped_at,
            needs_restart=runtime.needs_restart,
        )


def build_gateway_manager(settings: Settings) -> GatewayManager:
    return NativeGatewayManager(settings, build_systemd_controller(settings))
