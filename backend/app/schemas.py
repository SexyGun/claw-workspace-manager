from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.constants import GATEWAY_STATE_STOPPED, USER_ROLE_ADMIN, USER_ROLE_USER


class MessageResponse(BaseModel):
    message: str


class UserBase(BaseModel):
    username: str
    role: Literal["admin", "user"] = USER_ROLE_USER
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None


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


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    status: str | None = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    name: str
    slug: str
    host_path: str
    template_version: str
    status: str
    created_at: datetime


class WorkspaceConfigPayload(BaseModel):
    values: dict[str, Any]


class WorkspaceConfigRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_payload: dict[str, Any] = Field(alias="schema", serialization_alias="schema")
    values: dict[str, Any]
    rendered_path: str
    rendered_at: datetime | None = None


class GatewayStatusResponse(BaseModel):
    state: str = GATEWAY_STATE_STOPPED
    container_name: str
    last_container_id: str | None = None
    last_error: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None


class WorkspaceSummary(BaseModel):
    workspace: WorkspaceRead
    nanobot_config: WorkspaceConfigRead
    gateway_config: WorkspaceConfigRead
    gateway_status: GatewayStatusResponse
