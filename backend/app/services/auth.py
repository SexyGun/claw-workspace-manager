from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.security import hash_password, verify_password


def authenticate_user(db: Session, username: str, password: str) -> models.User | None:
    user = db.scalar(select(models.User).where(models.User.username == username))
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, username: str, password: str, role: str, is_active: bool = True) -> models.User:
    user = models.User(username=username, password_hash=hash_password(password), role=role, is_active=is_active)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user: models.User, new_password: str) -> models.User:
    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
