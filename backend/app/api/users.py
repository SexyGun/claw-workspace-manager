from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.dependencies import get_admin_user
from app.schemas import MessageResponse, UserCreate, UserRead, UserResetPassword, UserUpdate
from app.services.auth import create_user, reset_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(_: models.User = Depends(get_admin_user), db: Session = Depends(get_db)) -> list[UserRead]:
    users = db.scalars(select(models.User).order_by(models.User.created_at.desc())).all()
    return [UserRead.model_validate(user) for user in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_api(payload: UserCreate, _: models.User = Depends(get_admin_user), db: Session = Depends(get_db)) -> UserRead:
    try:
        user = create_user(db, payload.username, payload.password, payload.role, payload.is_active)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from exc
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
def update_user_api(
    user_id: int,
    payload: UserUpdate,
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> UserRead:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
def reset_password_api(
    user_id: int,
    payload: UserResetPassword,
    _: models.User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    reset_password(db, user, payload.password)
    return MessageResponse(message="Password reset")
