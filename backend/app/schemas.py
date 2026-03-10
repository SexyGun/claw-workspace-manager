from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.constants import RUNTIME_STATE_STOPPED, USER_ROLE_USER, WORKSPACE_TYPE_BASE, WORKSPACE_TYPE_OPENCLAW


class MessageResponse(BaseModel):
    message: str


class UserBase(BaseModel):
    username: str
    role: Literal["admin", "user"] = USER_ROLE_USER
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    role: Optional[Literal["admin", "user"]] = None
    is_active: Optional[bool] = None


class UserResetPassword(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Literal["admin", "user"] = USER_ROLE_USER
    is_active: bool = True


class WorkspaceTypeRead(BaseModel):
    key: Literal["base", "openclaw"]
    label: str
    description: str


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    workspace_type: Literal["base", "openclaw"] = WORKSPACE_TYPE_BASE


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    status: Optional[str] = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    name: str
    slug: str
    workspace_type: Literal["base", "openclaw"] = WORKSPACE_TYPE_BASE
    host_path: str
    template_version: str
    status: str
    activation_state: Optional[Literal["active", "inactive", "error"]] = None
    created_at: datetime


class WorkspaceConfigPayload(BaseModel):
    values: dict[str, Any]


class WorkspaceConfigRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_payload: dict[str, Any] = Field(alias="schema", serialization_alias="schema")
    values: dict[str, Any]
    rendered_path: str
    rendered_at: Optional[datetime] = None
    warnings: list[str] = Field(default_factory=list)


class OpenClawConfigPayload(BaseModel):
    structured_values: dict[str, Any] = Field(default_factory=dict)
    raw_json5: Optional[str] = None


class OpenClawChannelConfigPayload(BaseModel):
    values: dict[str, Any]


class OpenClawConfigRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_payload: dict[str, Any] = Field(alias="schema", serialization_alias="schema")
    values: dict[str, Any]
    raw_json5: str
    rendered_path: str
    rendered_at: Optional[datetime] = None


class RuntimeStatusResponse(BaseModel):
    state: str = RUNTIME_STATE_STOPPED
    scope: str
    controller_kind: str
    unit_name: Optional[str] = None
    process_id: Optional[int] = None
    listen_port: Optional[int] = None
    config_path: Optional[str] = None
    workspace_path: Optional[str] = None
    last_error: Optional[str] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    needs_restart: bool = False


class OpenClawRouteRead(BaseModel):
    agent_id: str
    channel: str
    account_id: str
    enabled: bool


class WorkspaceSummary(BaseModel):
    workspace: WorkspaceRead
    nanobot_config: Optional[WorkspaceConfigRead] = None
    runtime_status: Optional[RuntimeStatusResponse] = None
    openclaw_config: Optional[OpenClawConfigRead] = None
    openclaw_channel_config: Optional[WorkspaceConfigRead] = None
    openclaw_route: Optional[OpenClawRouteRead] = None
    shared_runtime_status: Optional[RuntimeStatusResponse] = None
