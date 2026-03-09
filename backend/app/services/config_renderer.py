from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def write_nanobot_config(file_path: Path, payload: dict[str, Any]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return datetime.now(timezone.utc)


def write_gateway_config(file_path: Path, payload: dict[str, Any]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return datetime.now(timezone.utc)
