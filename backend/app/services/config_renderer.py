from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import json5
import yaml

from app.config import Settings
from app.constants import MASKED_VALUE, SENSITIVE_CHANNEL_FIELDS


CHANNEL_SCHEMA: dict[str, Any] = {
    "title": "Nanobot Channels",
    "type": "object",
    "sections": [
        {
            "key": "feishu",
            "title": "Feishu",
            "fields": [
                {"key": "enabled", "label": "Enabled", "type": "boolean"},
                {"key": "app_id", "label": "App ID", "type": "text"},
                {"key": "app_secret", "label": "App Secret", "type": "password", "sensitive": True},
                {"key": "webhook", "label": "Webhook", "type": "text", "sensitive": True},
            ],
        },
        {
            "key": "dingtalk",
            "title": "DingTalk",
            "fields": [
                {"key": "enabled", "label": "Enabled", "type": "boolean"},
                {"key": "app_key", "label": "App Key", "type": "text"},
                {"key": "app_secret", "label": "App Secret", "type": "password", "sensitive": True},
                {"key": "robot_code", "label": "Robot Code", "type": "text"},
                {"key": "webhook", "label": "Webhook", "type": "text", "sensitive": True},
            ],
        },
        {
            "key": "qq",
            "title": "QQ",
            "fields": [
                {"key": "enabled", "label": "Enabled", "type": "boolean"},
                {"key": "bot_uin", "label": "Bot UIN", "type": "text"},
                {"key": "token", "label": "Token", "type": "password", "sensitive": True},
                {"key": "websocket_url", "label": "WebSocket URL", "type": "text"},
            ],
        },
    ],
}

GATEWAY_SCHEMA: dict[str, Any] = {
    "title": "Gateway",
    "type": "object",
    "fields": [
        {"key": "enabled", "label": "Enabled", "type": "boolean"},
        {"key": "listen_host", "label": "Listen Host", "type": "text"},
        {"key": "listen_port", "label": "Listen Port", "type": "number"},
        {
            "key": "default_channel",
            "label": "Default Channel",
            "type": "select",
            "options": ["feishu", "dingtalk", "qq"],
        },
        {"key": "log_level", "label": "Log Level", "type": "select", "options": ["debug", "info", "warning", "error"]},
    ],
}

OPENCLAW_SCHEMA: dict[str, Any] = {
    "title": "OpenClaw Config",
    "type": "object",
    "fields": [
        {"key": "gateway_port", "label": "Gateway Port", "type": "number"},
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

OPENCLAW_FALLBACK_SEPARATOR = ","
OPENCLAW_WORKSPACE_PATH = "~/.openclaw/workspace"


def default_channel_config() -> dict[str, Any]:
    return {
        "feishu": {"enabled": False, "app_id": "", "app_secret": "", "webhook": ""},
        "dingtalk": {"enabled": False, "app_key": "", "app_secret": "", "robot_code": "", "webhook": ""},
        "qq": {"enabled": False, "bot_uin": "", "token": "", "websocket_url": ""},
    }


def default_gateway_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "listen_host": "0.0.0.0",
        "listen_port": 8080,
        "default_channel": "feishu",
        "log_level": "info",
    }


def default_openclaw_config() -> dict[str, Any]:
    return normalize_openclaw_config(
        {
            "gateway": {"port": 7331},
            "agents": {
                "defaults": {
                    "model": {"primary": "gpt-4.1", "fallbacks": []},
                    "sandbox": {"mode": "workspace-write"},
                }
            },
            "session": {"dmScope": "workspace"},
            "hooks": {"enabled": False, "path": ".openclaw/hooks.js", "token": ""},
            "cron": {"enabled": False, "maxConcurrentRuns": 1},
        }
    )


def deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in extra.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def get_nested_value(data: dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def set_nested_value(data: dict[str, Any], path: Iterable[str], value: Any) -> None:
    path_list = list(path)
    current = data
    for key in path_list[:-1]:
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    current[path_list[-1]] = value


def merge_channel_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(default_channel_config())
    existing = existing or {}

    for section in merged:
        merged[section].update(existing.get(section, {}))

    for section in CHANNEL_SCHEMA["sections"]:
        section_key = section["key"]
        input_section = incoming.get(section_key, {})
        if not isinstance(input_section, dict):
            continue
        for field in section["fields"]:
            field_key = field["key"]
            if field_key not in input_section:
                continue
            next_value = input_section[field_key]
            if field.get("sensitive") and next_value == MASKED_VALUE:
                continue
            merged[section_key][field_key] = next_value
    return merged


def merge_gateway_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = default_gateway_config()
    merged.update(existing or {})
    for field in GATEWAY_SCHEMA["fields"]:
        key = field["key"]
        if key in incoming:
            merged[key] = incoming[key]
    return merged


def mask_channel_config(values: dict[str, Any]) -> dict[str, Any]:
    masked = copy.deepcopy(values or default_channel_config())
    for section_key, section_values in masked.items():
        for field_key in list(section_values.keys()):
            if (section_key, field_key) in SENSITIVE_CHANNEL_FIELDS and section_values[field_key]:
                section_values[field_key] = MASKED_VALUE
    return masked


def validate_channel_config(values: dict[str, Any]) -> dict[str, Any]:
    merged = merge_channel_config({}, values)
    for section in CHANNEL_SCHEMA["sections"]:
        section_key = section["key"]
        for field in section["fields"]:
            value = merged[section_key][field["key"]]
            if field["type"] == "boolean" and not isinstance(value, bool):
                raise ValueError(f"{section_key}.{field['key']} must be boolean")
    return merged


def validate_gateway_config(values: dict[str, Any]) -> dict[str, Any]:
    merged = merge_gateway_config({}, values)
    if not isinstance(merged["enabled"], bool):
        raise ValueError("enabled must be boolean")
    if not isinstance(merged["listen_port"], int):
        raise ValueError("listen_port must be integer")
    if merged["default_channel"] not in {"feishu", "dingtalk", "qq"}:
        raise ValueError("default_channel must be one of feishu, dingtalk, qq")
    if merged["log_level"] not in {"debug", "info", "warning", "error"}:
        raise ValueError("log_level must be a supported level")
    return merged


def normalize_openclaw_config(values: dict[str, Any]) -> dict[str, Any]:
    merged = deep_merge(default_openclaw_config_base(), values or {})
    set_nested_value(merged, ["agents", "defaults", "workspace"], OPENCLAW_WORKSPACE_PATH)
    return merged


def default_openclaw_config_base() -> dict[str, Any]:
    return {
        "gateway": {"port": 7331},
        "agents": {
            "defaults": {
                "workspace": OPENCLAW_WORKSPACE_PATH,
                "model": {"primary": "gpt-4.1", "fallbacks": []},
                "sandbox": {"mode": "workspace-write"},
            }
        },
        "session": {"dmScope": "workspace"},
        "hooks": {"enabled": False, "path": ".openclaw/hooks.js", "token": ""},
        "cron": {"enabled": False, "maxConcurrentRuns": 1},
    }


def extract_openclaw_structured_values(values: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_openclaw_config(values or {})
    fallbacks = get_nested_value(normalized, ["agents", "defaults", "model", "fallbacks"], [])
    if isinstance(fallbacks, list):
        fallback_text = f"{OPENCLAW_FALLBACK_SEPARATOR} ".join(str(item) for item in fallbacks)
    else:
        fallback_text = ""
    return {
        "gateway_port": get_nested_value(normalized, ["gateway", "port"], 7331),
        "primary_model": get_nested_value(normalized, ["agents", "defaults", "model", "primary"], ""),
        "fallback_models": fallback_text,
        "sandbox_mode": get_nested_value(normalized, ["agents", "defaults", "sandbox", "mode"], "workspace-write"),
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

    if "gateway_port" in incoming:
        set_nested_value(merged, ["gateway", "port"], incoming["gateway_port"])
    if "primary_model" in incoming:
        set_nested_value(merged, ["agents", "defaults", "model", "primary"], incoming["primary_model"])
    if "fallback_models" in incoming:
        raw_fallbacks = incoming["fallback_models"]
        if isinstance(raw_fallbacks, str):
            models = [item.strip() for item in raw_fallbacks.split(OPENCLAW_FALLBACK_SEPARATOR) if item.strip()]
        elif isinstance(raw_fallbacks, list):
            models = [str(item).strip() for item in raw_fallbacks if str(item).strip()]
        else:
            raise ValueError("fallback_models must be a string or list")
        set_nested_value(merged, ["agents", "defaults", "model", "fallbacks"], models)
    if "sandbox_mode" in incoming:
        set_nested_value(merged, ["agents", "defaults", "sandbox", "mode"], incoming["sandbox_mode"])
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
    if not isinstance(checks["gateway_port"], int):
        raise ValueError("gateway.port must be integer")
    if not isinstance(checks["primary_model"], str):
        raise ValueError("agents.defaults.model.primary must be string")
    if not isinstance(checks["fallback_models"], str):
        raise ValueError("agents.defaults.model.fallbacks must be serializable")
    if checks["sandbox_mode"] not in {"workspace-write", "read-only", "danger-full-access"}:
        raise ValueError("agents.defaults.sandbox.mode is not supported")
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


def load_openclaw_template_config(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return default_openclaw_config()
    return validate_openclaw_config(parse_openclaw_raw_json5(file_path.read_text(encoding="utf-8")))


def openclaw_raw_json(values: dict[str, Any]) -> str:
    return json.dumps(validate_openclaw_config(values or {}), indent=2, ensure_ascii=False) + "\n"


def render_nanobot_payload(workspace_name: str, workspace_slug: str, channel_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "workspace": {"name": workspace_name, "slug": workspace_slug},
        "channels": channel_config,
    }


def render_gateway_payload(
    workspace_id: int,
    workspace_name: str,
    gateway_config: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "enabled": gateway_config["enabled"],
        "listen": {
            "host": gateway_config["listen_host"],
            "port": gateway_config["listen_port"],
        },
        "default_channel": gateway_config["default_channel"],
        "log_level": gateway_config["log_level"],
        "nanobot_config": settings.nanobot_config_path,
    }


def render_openclaw_payload(openclaw_config: dict[str, Any]) -> dict[str, Any]:
    return validate_openclaw_config(openclaw_config)


def write_nanobot_config(file_path: Path, payload: dict[str, Any]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return datetime.now(timezone.utc)


def write_gateway_config(file_path: Path, payload: dict[str, Any]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return datetime.now(timezone.utc)


def write_openclaw_config(file_path: Path, payload: dict[str, Any]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(openclaw_raw_json(payload), encoding="utf-8")
    return datetime.now(timezone.utc)
