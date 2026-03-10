from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import json5

from app.config import Settings
from app.constants import MASKED_VALUE
from app.services.config_shared import deep_merge, get_nested_value, set_nested_value


OPENCLAW_SCHEMA: dict[str, Any] = {
    "title": "OpenClaw Agent",
    "type": "object",
    "fields": [
        {"key": "primary_model", "label": "Primary Model", "type": "text"},
        {
            "key": "fallback_models",
            "label": "Fallback Models",
            "type": "textarea",
            "placeholder": "model-a, model-b",
        },
        {
            "key": "sandbox_mode",
            "label": "Sandbox Mode",
            "type": "select",
            "options": ["workspace-write", "read-only", "danger-full-access"],
        },
        {
            "key": "session_dm_scope",
            "label": "Session DM Scope",
            "type": "select",
            "options": ["workspace", "user"],
        },
        {"key": "hooks_enabled", "label": "Hooks Enabled", "type": "boolean"},
        {"key": "hooks_path", "label": "Hooks Path", "type": "text"},
        {"key": "hooks_token", "label": "Hooks Token", "type": "password"},
        {"key": "cron_enabled", "label": "Cron Enabled", "type": "boolean"},
        {"key": "cron_max_concurrent_runs", "label": "Cron Max Concurrent Runs", "type": "number"},
    ],
}

OPENCLAW_CHANNEL_SCHEMA: dict[str, Any] = {
    "title": "OpenClaw Feishu Account",
    "type": "object",
    "fields": [
        {"key": "enabled", "label": "Enabled", "type": "boolean"},
        {"key": "account_id", "label": "Account ID", "type": "text"},
        {"key": "app_id", "label": "App ID", "type": "text"},
        {"key": "app_secret", "label": "App Secret", "type": "password", "sensitive": True},
    ],
}

OPENCLAW_FALLBACK_SEPARATOR = ","


def default_openclaw_config_base() -> dict[str, Any]:
    return {
        "model": {"primary": "gpt-4.1", "fallbacks": []},
        "sandbox": {"mode": "workspace-write"},
        "session": {"dmScope": "workspace"},
        "hooks": {"enabled": False, "path": ".openclaw/hooks.js", "token": ""},
        "cron": {"enabled": False, "maxConcurrentRuns": 1},
    }


def default_openclaw_config() -> dict[str, Any]:
    return normalize_openclaw_config(default_openclaw_config_base())


def default_openclaw_channel_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "account_id": "",
        "app_id": "",
        "app_secret": "",
    }


def default_openclaw_binding_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "channel": "feishu",
    }


def normalize_openclaw_config(values: dict[str, Any]) -> dict[str, Any]:
    return deep_merge(default_openclaw_config_base(), values or {})


def extract_openclaw_structured_values(values: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_openclaw_config(values or {})
    fallbacks = get_nested_value(normalized, ["model", "fallbacks"], [])
    fallback_text = (
        f"{OPENCLAW_FALLBACK_SEPARATOR} ".join(str(item) for item in fallbacks)
        if isinstance(fallbacks, list)
        else ""
    )
    return {
        "primary_model": get_nested_value(normalized, ["model", "primary"], ""),
        "fallback_models": fallback_text,
        "sandbox_mode": get_nested_value(normalized, ["sandbox", "mode"], "workspace-write"),
        "session_dm_scope": get_nested_value(normalized, ["session", "dmScope"], "workspace"),
        "hooks_enabled": get_nested_value(normalized, ["hooks", "enabled"], False),
        "hooks_path": get_nested_value(normalized, ["hooks", "path"], ".openclaw/hooks.js"),
        "hooks_token": get_nested_value(normalized, ["hooks", "token"], ""),
        "cron_enabled": get_nested_value(normalized, ["cron", "enabled"], False),
        "cron_max_concurrent_runs": get_nested_value(normalized, ["cron", "maxConcurrentRuns"], 1),
    }


def parse_openclaw_raw_json5(raw_json5: str) -> dict[str, Any]:
    try:
        parsed = json5.loads(raw_json5)
    except Exception as exc:
        raise ValueError(f"invalid openclaw json5: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("openclaw raw config must be a JSON object")
    return parsed


def merge_openclaw_structured_values(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = normalize_openclaw_config(existing or {})
    if "primary_model" in incoming:
        set_nested_value(merged, ["model", "primary"], incoming["primary_model"])
    if "fallback_models" in incoming:
        raw_fallbacks = incoming["fallback_models"]
        if isinstance(raw_fallbacks, str):
            models = [item.strip() for item in raw_fallbacks.split(OPENCLAW_FALLBACK_SEPARATOR) if item.strip()]
        elif isinstance(raw_fallbacks, list):
            models = [str(item).strip() for item in raw_fallbacks if str(item).strip()]
        else:
            raise ValueError("fallback_models must be a string or list")
        set_nested_value(merged, ["model", "fallbacks"], models)
    if "sandbox_mode" in incoming:
        set_nested_value(merged, ["sandbox", "mode"], incoming["sandbox_mode"])
    if "session_dm_scope" in incoming:
        set_nested_value(merged, ["session", "dmScope"], incoming["session_dm_scope"])
    if "hooks_enabled" in incoming:
        set_nested_value(merged, ["hooks", "enabled"], incoming["hooks_enabled"])
    if "hooks_path" in incoming:
        set_nested_value(merged, ["hooks", "path"], incoming["hooks_path"])
    if "hooks_token" in incoming:
        set_nested_value(merged, ["hooks", "token"], incoming["hooks_token"])
    if "cron_enabled" in incoming:
        set_nested_value(merged, ["cron", "enabled"], incoming["cron_enabled"])
    if "cron_max_concurrent_runs" in incoming:
        set_nested_value(merged, ["cron", "maxConcurrentRuns"], incoming["cron_max_concurrent_runs"])
    return normalize_openclaw_config(merged)


def validate_openclaw_config(values: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_openclaw_config(values or {})
    checks = extract_openclaw_structured_values(normalized)
    if not isinstance(checks["primary_model"], str):
        raise ValueError("model.primary must be string")
    if not isinstance(checks["fallback_models"], str):
        raise ValueError("model.fallbacks must be serializable")
    if checks["sandbox_mode"] not in {"workspace-write", "read-only", "danger-full-access"}:
        raise ValueError("sandbox.mode is not supported")
    if checks["session_dm_scope"] not in {"workspace", "user"}:
        raise ValueError("session.dmScope is not supported")
    if not isinstance(checks["hooks_enabled"], bool):
        raise ValueError("hooks.enabled must be boolean")
    if not isinstance(checks["hooks_path"], str):
        raise ValueError("hooks.path must be string")
    if not isinstance(checks["hooks_token"], str):
        raise ValueError("hooks.token must be string")
    if not isinstance(checks["cron_enabled"], bool):
        raise ValueError("cron.enabled must be boolean")
    if not isinstance(checks["cron_max_concurrent_runs"], int):
        raise ValueError("cron.maxConcurrentRuns must be integer")
    return normalized


def merge_openclaw_channel_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = default_openclaw_channel_config()
    merged.update(existing or {})
    for field in OPENCLAW_CHANNEL_SCHEMA["fields"]:
        key = field["key"]
        if key not in incoming:
            continue
        next_value = incoming[key]
        if field.get("sensitive") and next_value == MASKED_VALUE:
            continue
        merged[key] = next_value
    return merged


def merge_openclaw_binding_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = default_openclaw_binding_config()
    merged.update(existing or {})
    if "enabled" in incoming:
        merged["enabled"] = incoming["enabled"]
    return merged


def validate_openclaw_channel_config(values: dict[str, Any]) -> dict[str, Any]:
    merged = merge_openclaw_channel_config({}, values)
    if not isinstance(merged["enabled"], bool):
        raise ValueError("enabled must be boolean")
    for key in ["account_id", "app_id", "app_secret"]:
        if not isinstance(merged[key], str):
            raise ValueError(f"{key} must be string")
    if merged["enabled"]:
        for key in ["account_id", "app_id", "app_secret"]:
            if not merged[key].strip():
                raise ValueError(f"{key} is required when OpenClaw Feishu route is enabled")
    return merged


def validate_openclaw_binding_config(values: dict[str, Any]) -> dict[str, Any]:
    merged = merge_openclaw_binding_config({}, values)
    if not isinstance(merged["enabled"], bool):
        raise ValueError("enabled must be boolean")
    if merged.get("channel") != "feishu":
        raise ValueError("only feishu channel is supported")
    return merged


def load_openclaw_template_config(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return default_openclaw_config()
    raw_values = parse_openclaw_raw_json5(file_path.read_text(encoding="utf-8"))
    if "agents" in raw_values:
        raw_values = {
            "model": get_nested_value(raw_values, ["agents", "defaults", "model"], {}),
            "sandbox": get_nested_value(raw_values, ["agents", "defaults", "sandbox"], {}),
            "session": raw_values.get("session", {}),
            "hooks": raw_values.get("hooks", {}),
            "cron": raw_values.get("cron", {}),
        }
    return validate_openclaw_config(raw_values)


def openclaw_raw_json(values: dict[str, Any]) -> str:
    return json.dumps(validate_openclaw_config(values or {}), indent=2, ensure_ascii=False) + "\n"


def write_openclaw_config(file_path: Path, payload: dict[str, Any]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(openclaw_raw_json(payload), encoding="utf-8")
    return datetime.now(timezone.utc)


def mask_openclaw_channel_config(values: dict[str, Any]) -> dict[str, Any]:
    masked = copy.deepcopy(values or default_openclaw_channel_config())
    if masked.get("app_secret"):
        masked["app_secret"] = MASKED_VALUE
    return masked


def render_openclaw_workspace_payload(openclaw_config: dict[str, Any]) -> dict[str, Any]:
    return validate_openclaw_config(openclaw_config)


def openclaw_agent_id(workspace_id: int) -> str:
    return f"workspace-{workspace_id}"


def build_openclaw_route(channel_config: dict[str, Any], binding_config: dict[str, Any], workspace_id: int) -> dict[str, Any]:
    validated_channel = validate_openclaw_channel_config(channel_config)
    validated_binding = validate_openclaw_binding_config(binding_config)
    return {
        "enabled": bool(validated_binding["enabled"] and validated_channel["enabled"]),
        "channel": validated_binding["channel"],
        "account_id": validated_channel["account_id"],
        "agent_id": openclaw_agent_id(workspace_id),
    }


def render_openclaw_aggregate_payload(workspaces: list[dict[str, Any]], settings: Settings) -> dict[str, Any]:
    accounts: list[dict[str, Any]] = []
    agents: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    seen_account_ids: set[str] = set()
    for item in workspaces:
        workspace = item["workspace"]
        agent_config = validate_openclaw_config(item["openclaw_config"])
        channel_config = validate_openclaw_channel_config(item["openclaw_channel"])
        binding_config = validate_openclaw_binding_config(item["openclaw_binding"])
        route = build_openclaw_route(channel_config, binding_config, workspace.id)
        agent_id = route["agent_id"]
        agents.append(
            {
                "id": agent_id,
                "name": workspace.name,
                "workspace": item["workspace_path"],
                **copy.deepcopy(agent_config),
            }
        )
        if route["enabled"]:
            if route["account_id"] not in seen_account_ids:
                accounts.append(
                    {
                        "id": route["account_id"],
                        "appId": channel_config["app_id"],
                        "appSecret": channel_config["app_secret"],
                    }
                )
                seen_account_ids.add(route["account_id"])
            bindings.append(
                {
                    "channel": route["channel"],
                    "accountId": route["account_id"],
                    "agentId": agent_id,
                }
            )

    return {
        "gateway": {"port": settings.openclaw_gateway_port},
        "channels": {"feishu": {"accounts": accounts}},
        "agents": {"list": agents},
        "bindings": bindings,
    }
