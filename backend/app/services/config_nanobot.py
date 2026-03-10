from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from app.constants import MASKED_VALUE, SENSITIVE_CHANNEL_FIELDS
from app.services.config_shared import deep_merge, section_dict, string_value


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
            ],
        },
        {
            "key": "dingtalk",
            "title": "DingTalk",
            "fields": [
                {"key": "enabled", "label": "Enabled", "type": "boolean"},
                {"key": "client_id", "label": "Client ID", "type": "text"},
                {"key": "client_secret", "label": "Client Secret", "type": "password", "sensitive": True},
            ],
        },
        {
            "key": "qq",
            "title": "QQ",
            "fields": [
                {"key": "enabled", "label": "Enabled", "type": "boolean"},
                {"key": "app_id", "label": "App ID", "type": "text"},
                {"key": "secret", "label": "Secret", "type": "password", "sensitive": True},
            ],
        },
    ],
}

PROVIDER_SECTIONS: list[tuple[str, str]] = [
    ("custom", "Custom"),
    ("azure_openai", "Azure OpenAI"),
    ("anthropic", "Anthropic"),
    ("openai", "OpenAI"),
    ("openrouter", "OpenRouter"),
    ("deepseek", "DeepSeek"),
    ("groq", "Groq"),
    ("zhipu", "Zhipu AI"),
    ("dashscope", "DashScope"),
    ("vllm", "vLLM / Local"),
    ("gemini", "Gemini"),
    ("moonshot", "Moonshot"),
    ("minimax", "MiniMax"),
    ("aihubmix", "AiHubMix"),
    ("siliconflow", "SiliconFlow"),
    ("volcengine", "VolcEngine"),
    ("openai_codex", "OpenAI Codex"),
    ("github_copilot", "Github Copilot"),
]

PROVIDER_SCHEMA: dict[str, Any] = {
    "title": "Nanobot Providers",
    "type": "object",
    "sections": [
        {
            "key": key,
            "title": title,
            "fields": [
                {"key": "api_key", "label": "API Key", "type": "password", "sensitive": True},
                {"key": "api_base", "label": "API Base", "type": "text"},
                {
                    "key": "extra_headers_json",
                    "label": "Extra Headers JSON",
                    "type": "textarea",
                    "placeholder": '{"APP-Code":"..."}',
                },
            ],
        }
        for key, title in PROVIDER_SECTIONS
    ],
}

AGENT_DEFAULTS_SCHEMA: dict[str, Any] = {
    "title": "Nanobot Agent Defaults",
    "type": "object",
    "fields": [
        {"key": "model", "label": "Model", "type": "text"},
        {
            "key": "provider",
            "label": "Provider",
            "type": "select",
            "options": ["auto"] + [key for key, _ in PROVIDER_SECTIONS],
        },
    ],
}

GATEWAY_SCHEMA: dict[str, Any] = {
    "title": "Gateway",
    "type": "object",
    "fields": [
        {"key": "enabled", "label": "Enabled", "type": "boolean"},
        {"key": "listen_host", "label": "Listen Host", "type": "text", "readonly": True},
        {"key": "listen_port", "label": "Listen Port", "type": "number", "readonly": True},
        {
            "key": "default_channel",
            "label": "Default Channel",
            "type": "select",
            "options": ["feishu", "dingtalk", "qq"],
        },
        {"key": "log_level", "label": "Log Level", "type": "select", "options": ["debug", "info", "warning", "error"]},
    ],
}

QQ_LEGACY_MIGRATION_WARNING = "QQ legacy config could not be migrated automatically; re-enter App ID and Secret."
NANOBOT_ALLOWED_TOP_LEVEL_KEYS = {"agents", "channels", "providers", "gateway", "tools"}
CHANNEL_ALLOW_ALL = ["*"]

NANOBOT_LEGACY_CHANNEL_FIELDS: dict[str, set[str]] = {
    "feishu": {"webhook"},
    "dingtalk": {"app_key", "app_secret", "robot_code", "webhook"},
    "qq": {"bot_uin", "token", "websocket_url"},
}


def default_channel_config() -> dict[str, Any]:
    return {
        "feishu": {"enabled": False, "app_id": "", "app_secret": ""},
        "dingtalk": {"enabled": False, "client_id": "", "client_secret": ""},
        "qq": {"enabled": False, "app_id": "", "secret": ""},
    }


def default_gateway_config() -> dict[str, Any]:
    return {
        "listen_host": "127.0.0.1",
        "listen_port": 18080,
    }


def default_provider_config() -> dict[str, Any]:
    return {
        key: {
            "api_key": "",
            "api_base": "",
            "extra_headers_json": "",
        }
        for key, _ in PROVIDER_SECTIONS
    }


def default_agent_defaults_config() -> dict[str, Any]:
    return {
        "model": "anthropic/claude-opus-4-5",
        "provider": "auto",
    }


def default_nanobot_instance_config() -> dict[str, Any]:
    return {
        "agents": {
            "defaults": {
                "workspace": "~/.nanobot/workspace",
                "model": "anthropic/claude-opus-4-5",
                "provider": "auto",
                "max_tokens": 8192,
                "temperature": 0.1,
                "max_tool_iterations": 40,
                "memory_window": 100,
                "reasoning_effort": None,
            }
        },
        "channels": {
            "send_progress": True,
            "send_tool_hints": False,
            "feishu": {
                "enabled": False,
                "app_id": "",
                "app_secret": "",
                "encrypt_key": "",
                "verification_token": "",
                "allowFrom": ["*"],
                "react_emoji": "THUMBSUP",
            },
            "dingtalk": {
                "enabled": False,
                "client_id": "",
                "client_secret": "",
                "allowFrom": ["*"],
            },
            "qq": {
                "enabled": False,
                "app_id": "",
                "secret": "",
                "allowFrom": ["*"],
            },
        },
        "providers": {},
        "gateway": {
            "host": "0.0.0.0",
            "port": 18790,
            "heartbeat": {"enabled": True, "interval_s": 1800},
        },
        "tools": {
            "web": {"proxy": None, "search": {"api_key": "", "max_results": 5}},
            "exec": {"timeout": 60, "path_append": ""},
            "restrict_to_workspace": False,
            "mcp_servers": {},
        },
    }


def provider_section_to_form(section: dict[str, Any]) -> dict[str, Any]:
    extra_headers = section.get("extra_headers")
    extra_headers_json = ""
    if isinstance(extra_headers, dict) and extra_headers:
        extra_headers_json = json.dumps(extra_headers, indent=2, ensure_ascii=False)
    return {
        "api_key": string_value(section.get("api_key")),
        "api_base": string_value(section.get("api_base")),
        "extra_headers_json": extra_headers_json,
    }


def extract_agent_defaults_config(values: dict[str, Any] | None) -> dict[str, Any]:
    defaults = values.get("agents", {}).get("defaults", {}) if isinstance(values, dict) else {}
    if not isinstance(defaults, dict):
        defaults = {}
    extracted = default_agent_defaults_config()
    extracted["model"] = string_value(defaults.get("model")) or extracted["model"]
    extracted["provider"] = string_value(defaults.get("provider")) or extracted["provider"]
    return extracted


def extract_provider_config(values: dict[str, Any] | None) -> dict[str, Any]:
    providers = values.get("providers", {}) if isinstance(values, dict) else {}
    extracted = copy.deepcopy(default_provider_config())
    for key, _ in PROVIDER_SECTIONS:
        section = providers.get(key, {})
        if isinstance(section, dict):
            extracted[key] = provider_section_to_form(section)
    return extracted


def normalize_channel_config(values: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    normalized = copy.deepcopy(default_channel_config())
    warnings: list[str] = []
    values = values or {}

    feishu = section_dict(values, "feishu")
    normalized["feishu"].update(
        {
            "enabled": bool(feishu.get("enabled", False)),
            "app_id": string_value(feishu.get("app_id")),
            "app_secret": string_value(feishu.get("app_secret")),
        }
    )

    dingtalk = section_dict(values, "dingtalk")
    normalized["dingtalk"].update(
        {
            "enabled": bool(dingtalk.get("enabled", False)),
            "client_id": string_value(dingtalk.get("client_id") or dingtalk.get("app_key")),
            "client_secret": string_value(dingtalk.get("client_secret") or dingtalk.get("app_secret")),
        }
    )

    qq = section_dict(values, "qq")
    has_legacy_qq = any(string_value(qq.get(key)) for key in NANOBOT_LEGACY_CHANNEL_FIELDS["qq"])
    normalized["qq"].update(
        {
            "enabled": bool(qq.get("enabled", False)),
            "app_id": string_value(qq.get("app_id")),
            "secret": string_value(qq.get("secret")),
        }
    )
    if has_legacy_qq and not (normalized["qq"]["app_id"] or normalized["qq"]["secret"]):
        warnings.append(QQ_LEGACY_MIGRATION_WARNING)

    return normalized, warnings


def channel_config_warnings(values: dict[str, Any] | None) -> list[str]:
    _, warnings = normalize_channel_config(values)
    return warnings


def mask_provider_config(values: dict[str, Any] | None) -> dict[str, Any]:
    masked = extract_provider_config(values)
    for section_values in masked.values():
        if section_values["api_key"]:
            section_values["api_key"] = MASKED_VALUE
    return masked


def merge_channel_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged, _ = normalize_channel_config(existing)
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


def parse_extra_headers_json(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("extra_headers_json must be string")
    if not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"extra_headers_json must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("extra_headers_json must decode to a JSON object")
    result: dict[str, str] = {}
    for key, item in parsed.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError("extra_headers_json keys and values must be strings")
        result[key] = item
    return result


def merge_provider_config(existing_config: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged_config = deep_merge(default_nanobot_instance_config(), existing_config or {})
    current_form = extract_provider_config(merged_config)
    providers = merged_config.setdefault("providers", {})
    for section in PROVIDER_SCHEMA["sections"]:
        section_key = section["key"]
        input_section = incoming.get(section_key, {})
        if not isinstance(input_section, dict):
            continue
        current_values = current_form[section_key]
        next_values = copy.deepcopy(current_values)
        for field in section["fields"]:
            field_key = field["key"]
            if field_key not in input_section:
                continue
            next_value = input_section[field_key]
            if field.get("sensitive") and next_value == MASKED_VALUE:
                continue
            next_values[field_key] = next_value
        providers[section_key] = {
            "api_key": string_value(next_values["api_key"]),
            "api_base": string_value(next_values["api_base"]) or None,
            "extra_headers": parse_extra_headers_json(next_values["extra_headers_json"]),
        }
    return merged_config


def merge_agent_defaults_config(existing_config: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged_config = deep_merge(default_nanobot_instance_config(), existing_config or {})
    current_form = extract_agent_defaults_config(merged_config)
    next_values = copy.deepcopy(current_form)
    for field in AGENT_DEFAULTS_SCHEMA["fields"]:
        field_key = field["key"]
        if field_key not in incoming:
            continue
        next_values[field_key] = incoming[field_key]
    merged_config.setdefault("agents", {}).setdefault("defaults", {})
    merged_config["agents"]["defaults"]["model"] = string_value(next_values["model"]) or current_form["model"]
    merged_config["agents"]["defaults"]["provider"] = string_value(next_values["provider"]) or current_form["provider"]
    return merged_config


def merge_gateway_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = default_gateway_config()
    merged.update(existing or {})
    for field in GATEWAY_SCHEMA["fields"]:
        key = field["key"]
        if key not in incoming or field.get("readonly"):
            continue
        merged[key] = incoming[key]
    return merged


def mask_channel_config(values: dict[str, Any]) -> dict[str, Any]:
    masked, _ = normalize_channel_config(values)
    for section_key, section_values in masked.items():
        for field_key in list(section_values.keys()):
            if (section_key, field_key) in SENSITIVE_CHANNEL_FIELDS and section_values[field_key]:
                section_values[field_key] = MASKED_VALUE
    return masked


def validate_channel_config(values: dict[str, Any]) -> dict[str, Any]:
    merged, _ = normalize_channel_config(values)
    for section in CHANNEL_SCHEMA["sections"]:
        section_key = section["key"]
        for field in section["fields"]:
            value = merged[section_key][field["key"]]
            if field["type"] == "boolean" and not isinstance(value, bool):
                raise ValueError(f"{section_key}.{field['key']} must be boolean")
            if field["type"] in {"text", "password"} and not isinstance(value, str):
                raise ValueError(f"{section_key}.{field['key']} must be string")
    return merged


def validate_provider_config(values: dict[str, Any]) -> dict[str, Any]:
    merged = extract_provider_config(values)
    for section in PROVIDER_SCHEMA["sections"]:
        section_key = section["key"]
        section_values = merged[section_key]
        if not isinstance(section_values["api_key"], str):
            raise ValueError(f"{section_key}.api_key must be string")
        if not isinstance(section_values["api_base"], str):
            raise ValueError(f"{section_key}.api_base must be string")
        parse_extra_headers_json(section_values["extra_headers_json"])
    return merged


def validate_agent_defaults_config(values: dict[str, Any]) -> dict[str, Any]:
    merged = extract_agent_defaults_config(values)
    if not isinstance(merged["model"], str) or not merged["model"].strip():
        raise ValueError("agents.defaults.model must be non-empty string")
    if not isinstance(merged["provider"], str) or merged["provider"] not in AGENT_DEFAULTS_SCHEMA["fields"][1]["options"]:
        raise ValueError("agents.defaults.provider is not supported")
    return merged


def validate_gateway_config(values: dict[str, Any]) -> dict[str, Any]:
    merged = merge_gateway_config({}, values)
    if not isinstance(merged["listen_host"], str):
        raise ValueError("listen_host must be string")
    if not isinstance(merged["listen_port"], int):
        raise ValueError("listen_port must be integer")
    return merged


def load_nanobot_instance_config(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return default_nanobot_instance_config()
    try:
        raw_values = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid nanobot config json: {exc}") from exc
    if not isinstance(raw_values, dict):
        raise ValueError("nanobot config must be a JSON object")
    sanitized_values = {key: value for key, value in raw_values.items() if key in NANOBOT_ALLOWED_TOP_LEVEL_KEYS}
    return deep_merge(default_nanobot_instance_config(), sanitized_values)


def render_nanobot_config_payload(
    base_config: dict[str, Any],
    channel_config: dict[str, Any],
    workspace_path: str,
    gateway_host: str,
    gateway_port: int,
) -> dict[str, Any]:
    payload = deep_merge(default_nanobot_instance_config(), base_config or {})
    normalized_channels = validate_channel_config(channel_config)
    payload.setdefault("agents", {}).setdefault("defaults", {})
    payload["agents"]["defaults"]["workspace"] = workspace_path
    payload.setdefault("gateway", {})
    payload["gateway"]["host"] = gateway_host
    payload["gateway"]["port"] = gateway_port
    payload["channels"] = render_nanobot_channels(payload.get("channels", {}), normalized_channels)
    return payload


def render_nanobot_channels(existing_channels: dict[str, Any], managed_channels: dict[str, Any]) -> dict[str, Any]:
    channels = copy.deepcopy(existing_channels if isinstance(existing_channels, dict) else {})
    channels.setdefault("send_progress", True)
    channels.setdefault("send_tool_hints", False)
    for section_key, values in managed_channels.items():
        current = channels.get(section_key, {})
        current = copy.deepcopy(current if isinstance(current, dict) else {})
        for legacy_key in NANOBOT_LEGACY_CHANNEL_FIELDS.get(section_key, set()):
            current.pop(legacy_key, None)
        current.update(values)
        current = normalize_runtime_channel_section(section_key, current)
        channels[section_key] = current
    return channels


def normalize_runtime_channel_section(section_key: str, values: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(values if isinstance(values, dict) else {})
    allow_from = normalized.pop("allow_from", None)
    allow_from_value = normalized.get("allowFrom", allow_from)
    if isinstance(allow_from_value, list):
        allow_from_value = [item for item in allow_from_value if isinstance(item, str) and item]
    else:
        allow_from_value = []

    if section_key == "feishu" and not allow_from_value:
        normalized["allowFrom"] = CHANNEL_ALLOW_ALL.copy()
    elif allow_from_value:
        normalized["allowFrom"] = allow_from_value

    return normalized
