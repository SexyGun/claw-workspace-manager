from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.constants import USER_ROLE_ADMIN
from app.db import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = db.get(models.User, user_id)
    if not user or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_admin_user(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != USER_ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_workspace_for_user(
    workspace_id: int,
    current_user: models.User,
    db: Session,
) -> models.Workspace:
    workspace = db.get(models.Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    if current_user.role != USER_ROLE_ADMIN and workspace.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return workspace


def get_gateway_manager(request: Request):
    return request.app.state.gateway_manager


def get_app_settings():
    return get_settings()
