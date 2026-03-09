from __future__ import annotations

MASKED_VALUE = "__MASKED__"

USER_ROLE_ADMIN = "admin"
USER_ROLE_USER = "user"

WORKSPACE_STATUS_READY = "ready"

GATEWAY_STATE_STOPPED = "stopped"
GATEWAY_STATE_STARTING = "starting"
GATEWAY_STATE_RUNNING = "running"
GATEWAY_STATE_STOPPING = "stopping"
GATEWAY_STATE_ERROR = "error"

SENSITIVE_CHANNEL_FIELDS = {
    ("feishu", "app_secret"),
    ("feishu", "webhook"),
    ("dingtalk", "app_secret"),
    ("dingtalk", "webhook"),
    ("qq", "token"),
}
