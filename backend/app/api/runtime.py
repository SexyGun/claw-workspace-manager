from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.dependencies import get_admin_user, get_current_user, get_openclaw_manager
from app.schemas import RuntimeStatusResponse
from app.services.openclaw_runtime import OpenClawRuntimeManager
from app.services.runtime_control import RuntimeStatus

router = APIRouter(prefix="/runtime", tags=["runtime"])


def serialize_runtime_status(runtime: RuntimeStatus) -> RuntimeStatusResponse:
    return RuntimeStatusResponse(
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


@router.get("/openclaw/service", response_model=RuntimeStatusResponse)
def get_openclaw_service_status_api(
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    return serialize_runtime_status(openclaw_manager.service_status(db))


@router.post("/openclaw/service/start", response_model=RuntimeStatusResponse)
def start_openclaw_service_api(
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    return serialize_runtime_status(openclaw_manager.service_start(db))


@router.post("/openclaw/service/stop", response_model=RuntimeStatusResponse)
def stop_openclaw_service_api(
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    return serialize_runtime_status(openclaw_manager.service_stop(db))


@router.post("/openclaw/service/restart", response_model=RuntimeStatusResponse)
def restart_openclaw_service_api(
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    openclaw_manager: OpenClawRuntimeManager = Depends(get_openclaw_manager),
) -> RuntimeStatusResponse:
    return serialize_runtime_status(openclaw_manager.service_restart(db))
