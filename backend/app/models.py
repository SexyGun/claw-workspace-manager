from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.constants import (
    RUNTIME_CONTROLLER_SYSTEMD,
    RUNTIME_KIND_NANOBOT,
    RUNTIME_SCOPE_SHARED,
    RUNTIME_SCOPE_WORKSPACE,
    WORKSPACE_TYPE_BASE,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("owner_user_id", "slug", name="uq_owner_workspace_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    workspace_type: Mapped[str] = mapped_column(String(32), nullable=False, default=WORKSPACE_TYPE_BASE)
    host_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    template_version: Mapped[str] = mapped_column(String(64), nullable=False, default="base-workspace-v1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")

    owner: Mapped["User"] = relationship(back_populates="workspaces")
    config: Mapped["WorkspaceConfig"] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        uselist=False,
    )
    runtime: Mapped[Optional["WorkspaceRuntime"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        uselist=False,
    )


class WorkspaceConfig(Base):
    __tablename__ = "workspace_configs"

    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    channel_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    gateway_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    openclaw_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    openclaw_channel_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    openclaw_binding_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    nanobot_rendered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gateway_rendered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    openclaw_rendered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="config")


class WorkspaceRuntime(Base):
    __tablename__ = "workspace_runtimes"

    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    runtime_kind: Mapped[str] = mapped_column(String(32), nullable=False, default=RUNTIME_KIND_NANOBOT)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default=RUNTIME_SCOPE_WORKSPACE)
    controller_kind: Mapped[str] = mapped_column(String(32), nullable=False, default=RUNTIME_CONTROLLER_SYSTEMD)
    unit_name: Mapped[str] = mapped_column(String(255), nullable=False)
    process_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    listen_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="stopped")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    needs_restart: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="runtime")


class SharedRuntime(Base):
    __tablename__ = "shared_runtimes"

    runtime_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    runtime_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="openclaw")
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default=RUNTIME_SCOPE_SHARED)
    controller_kind: Mapped[str] = mapped_column(String(32), nullable=False, default=RUNTIME_CONTROLLER_SYSTEMD)
    unit_name: Mapped[str] = mapped_column(String(255), nullable=False)
    process_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="stopped")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    needs_restart: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
