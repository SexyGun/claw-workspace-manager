from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.constants import WORKSPACE_TYPE_BASE, WORKSPACE_TYPE_OPENCLAW


@dataclass(frozen=True)
class WorkspaceProfile:
    key: str
    label: str
    description: str
    template_version: str
    template_root: Path
    runtime_kind: str


def get_workspace_profiles(settings: Settings) -> dict[str, WorkspaceProfile]:
    return {
        WORKSPACE_TYPE_BASE: WorkspaceProfile(
            key=WORKSPACE_TYPE_BASE,
            label="Base Workspace",
            description="Nanobot and gateway workspace",
            template_version="base-workspace-v1",
            template_root=settings.workspace_template_root,
            runtime_kind="gateway",
        ),
        WORKSPACE_TYPE_OPENCLAW: WorkspaceProfile(
            key=WORKSPACE_TYPE_OPENCLAW,
            label="OpenClaw Workspace",
            description="OpenClaw workspace with dedicated runtime container",
            template_version="openclaw-workspace-v1",
            template_root=settings.openclaw_workspace_template_root,
            runtime_kind="openclaw",
        ),
    }


def get_workspace_profile(settings: Settings, workspace_type: str) -> WorkspaceProfile:
    profiles = get_workspace_profiles(settings)
    try:
        return profiles[workspace_type]
    except KeyError as exc:
        raise ValueError(f"unsupported workspace type: {workspace_type}") from exc
