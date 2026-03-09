from __future__ import annotations

MASKED_VALUE = "__MASKED__"

USER_ROLE_ADMIN = "admin"
USER_ROLE_USER = "user"

WORKSPACE_TYPE_BASE = "base"
WORKSPACE_TYPE_OPENCLAW = "openclaw"

WORKSPACE_STATUS_READY = "ready"

RUNTIME_SCOPE_WORKSPACE = "workspace"
RUNTIME_SCOPE_SHARED = "shared"
RUNTIME_SCOPE_ROUTE = "route"

RUNTIME_CONTROLLER_SYSTEMD = "systemd"
RUNTIME_CONTROLLER_NONE = "none"

RUNTIME_STATE_STOPPED = "stopped"
RUNTIME_STATE_STARTING = "starting"
RUNTIME_STATE_RUNNING = "running"
RUNTIME_STATE_STOPPING = "stopping"
RUNTIME_STATE_ERROR = "error"
RUNTIME_STATE_CONFIGURED = "configured"
RUNTIME_STATE_INACTIVE = "inactive"

RUNTIME_KIND_NANOBOT = "nanobot"
RUNTIME_KIND_OPENCLAW = "openclaw"

SHARED_RUNTIME_KEY_OPENCLAW = "openclaw"

SENSITIVE_CHANNEL_FIELDS = {
    ("feishu", "app_secret"),
    ("feishu", "webhook"),
    ("dingtalk", "app_secret"),
    ("dingtalk", "webhook"),
    ("qq", "token"),
    ("openclaw_feishu", "app_secret"),
}
