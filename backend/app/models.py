from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.constants import WORKSPACE_TYPE_BASE


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
    gateway_instance: Mapped["GatewayInstance"] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        uselist=False,
    )
    openclaw_instance: Mapped["OpenClawInstance"] = relationship(
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
    nanobot_rendered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gateway_rendered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    openclaw_rendered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="config")


class GatewayInstance(Base):
    __tablename__ = "gateway_instances"

    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    container_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="stopped")
    last_container_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="gateway_instance")


class OpenClawInstance(Base):
    __tablename__ = "openclaw_instances"

    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    container_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="stopped")
    last_container_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="openclaw_instance")
