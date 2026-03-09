from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.config import Settings
from app.constants import (
    RUNTIME_CONTROLLER_SYSTEMD,
    RUNTIME_KIND_OPENCLAW,
    RUNTIME_SCOPE_SHARED,
    RUNTIME_STATE_ERROR,
    RUNTIME_STATE_RUNNING,
    RUNTIME_STATE_STOPPED,
    SHARED_RUNTIME_KEY_OPENCLAW,
)
from app.services.runtime_control import (
    NullController,
    RuntimeControlError,
    RuntimeStatus,
    SystemdController,
    SystemdUnitStatus,
    build_systemd_controller,
)


class OpenClawRuntimeManager:
    def sync_managed_containers(self, db: Session) -> None:
        raise NotImplementedError

    def service_status(self, db: Session) -> RuntimeStatus:
        raise NotImplementedError

    def service_start(self, db: Session) -> RuntimeStatus:
        raise NotImplementedError

    def service_stop(self, db: Session) -> RuntimeStatus:
        raise NotImplementedError

    def service_restart(self, db: Session) -> RuntimeStatus:
        raise NotImplementedError

    def reload_if_running(self, db: Session) -> RuntimeStatus:
        raise NotImplementedError


class NativeOpenClawRuntimeManager(OpenClawRuntimeManager):
    def __init__(self, settings: Settings, controller: SystemdController | NullController):
        self.settings = settings
        self.controller = controller

    def sync_managed_containers(self, db: Session) -> None:
        self.service_status(db)

    def service_status(self, db: Session) -> RuntimeStatus:
        runtime = self._get_or_create_runtime(db)
        try:
            unit_status = self.controller.status(runtime.unit_name)
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            return self._save_error(db, runtime, str(exc))

    def service_start(self, db: Session) -> RuntimeStatus:
        runtime = self._get_or_create_runtime(db)
        try:
            unit_status = self.controller.start(runtime.unit_name)
            runtime.needs_restart = False
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            return self._save_error(db, runtime, str(exc))

    def service_stop(self, db: Session) -> RuntimeStatus:
        runtime = self._get_or_create_runtime(db)
        try:
            unit_status = self.controller.stop(runtime.unit_name)
            if unit_status.stopped_at is None:
                unit_status.stopped_at = datetime.now(timezone.utc)
            runtime.needs_restart = False
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            return self._save_error(db, runtime, str(exc))

    def service_restart(self, db: Session) -> RuntimeStatus:
        runtime = self._get_or_create_runtime(db)
        try:
            unit_status = self.controller.restart(runtime.unit_name)
            runtime.needs_restart = False
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            return self._save_error(db, runtime, str(exc))

    def reload_if_running(self, db: Session) -> RuntimeStatus:
        runtime = self._get_or_create_runtime(db)
        current = self.service_status(db)
        runtime = self._get_or_create_runtime(db)
        if current.state != RUNTIME_STATE_RUNNING:
            runtime.needs_restart = True
            db.add(runtime)
            db.commit()
            db.refresh(runtime)
            return self._to_status(runtime)
        try:
            unit_status = self.controller.reload(runtime.unit_name)
            runtime.needs_restart = False
            return self._save_status(db, runtime, unit_status)
        except RuntimeControlError as exc:
            runtime.needs_restart = True
            db.add(runtime)
            db.commit()
            db.refresh(runtime)
            return self._save_error(db, runtime, str(exc), keep_restart_flag=True)

    def _get_or_create_runtime(self, db: Session) -> models.SharedRuntime:
        runtime = db.get(models.SharedRuntime, SHARED_RUNTIME_KEY_OPENCLAW)
        if runtime is None:
            runtime = models.SharedRuntime(
                runtime_key=SHARED_RUNTIME_KEY_OPENCLAW,
                runtime_kind=RUNTIME_KIND_OPENCLAW,
                scope=RUNTIME_SCOPE_SHARED,
                controller_kind=RUNTIME_CONTROLLER_SYSTEMD,
                unit_name=self.settings.openclaw_shared_unit,
                state=RUNTIME_STATE_STOPPED,
            )
            db.add(runtime)
            db.commit()
            db.refresh(runtime)
        return runtime

    def _save_status(
        self,
        db: Session,
        runtime: models.SharedRuntime,
        unit_status: SystemdUnitStatus,
    ) -> RuntimeStatus:
        runtime.controller_kind = RUNTIME_CONTROLLER_SYSTEMD
        runtime.unit_name = unit_status.unit_name
        runtime.process_id = unit_status.process_id
        runtime.state = unit_status.state
        runtime.last_error = None
        runtime.started_at = unit_status.started_at
        runtime.stopped_at = unit_status.stopped_at if unit_status.state != RUNTIME_STATE_RUNNING else None
        db.add(runtime)
        db.commit()
        db.refresh(runtime)
        return self._to_status(runtime)

    def _save_error(
        self,
        db: Session,
        runtime: models.SharedRuntime,
        error: str,
        *,
        keep_restart_flag: bool = False,
    ) -> RuntimeStatus:
        runtime.state = RUNTIME_STATE_ERROR if not isinstance(self.controller, NullController) else RUNTIME_STATE_STOPPED
        runtime.last_error = error
        if not keep_restart_flag:
            runtime.needs_restart = runtime.needs_restart and runtime.state == RUNTIME_STATE_STOPPED
        db.add(runtime)
        db.commit()
        db.refresh(runtime)
        return self._to_status(runtime)

    def _to_status(self, runtime: models.SharedRuntime) -> RuntimeStatus:
        return RuntimeStatus(
            state=runtime.state,
            scope=runtime.scope,
            controller_kind=runtime.controller_kind,
            unit_name=runtime.unit_name,
            process_id=runtime.process_id,
            last_error=runtime.last_error,
            started_at=runtime.started_at,
            stopped_at=runtime.stopped_at,
            needs_restart=runtime.needs_restart,
        )


def build_openclaw_runtime_manager(settings: Settings) -> OpenClawRuntimeManager:
    return NativeOpenClawRuntimeManager(settings, build_systemd_controller(settings))
