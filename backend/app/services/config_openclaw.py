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


OPENCLAW_MODEL_API_OPTIONS = [
    "openai-completions",
    "openai-responses",
    "openai-codex-responses",
    "anthropic-messages",
    "google-generative-ai",
    "github-copilot",
    "bedrock-converse-stream",
    "ollama",
]
OPENCLAW_PROVIDER_AUTH_OPTIONS = ["api-key", "aws-sdk", "oauth", "token"]
OPENCLAW_SANDBOX_MODE_OPTIONS = ["off", "non-main", "all"]
OPENCLAW_SANDBOX_WORKSPACE_ACCESS_OPTIONS = ["none", "ro", "rw"]
OPENCLAW_SESSION_DM_SCOPE_OPTIONS = ["main", "per-peer", "per-channel-peer", "per-account-channel-peer"]
LEGACY_OPENCLAW_SANDBOX_MODES = {
    "workspace-write": {"mode": "non-main", "workspaceAccess": "rw"},
    "read-only": {"mode": "non-main", "workspaceAccess": "ro"},
    "danger-full-access": {"mode": "off"},
}
LEGACY_OPENCLAW_DM_SCOPES = {
    "workspace": "main",
    "user": "per-peer",
}

OPENCLAW_SCHEMA: dict[str, Any] = {
    "title": "OpenClaw Agent",
    "type": "object",
    "fields": [
        {"key": "primary_model", "label": "Primary Model", "type": "text"},
        {
            "key": "fallback_models",
            "label": "Fallback Models",
            "type": "textarea",
            "placeholder": "provider-a/model-a, provider-b/model-b",
        },
        {
            "key": "sandbox_mode",
            "label": "Sandbox Mode",
            "type": "select",
            "options": OPENCLAW_SANDBOX_MODE_OPTIONS,
        },
        {
            "key": "sandbox_workspace_access",
            "label": "Sandbox Workspace Access",
            "type": "select",
            "options": OPENCLAW_SANDBOX_WORKSPACE_ACCESS_OPTIONS,
        },
        {
            "key": "session_dm_scope",
            "label": "Session DM Scope",
            "type": "select",
            "options": OPENCLAW_SESSION_DM_SCOPE_OPTIONS,
        },
        {
            "key": "models_mode",
            "label": "Models Merge Mode",
            "type": "select",
            "options": ["merge", "replace"],
        },
        {"key": "provider_id", "label": "Primary Provider ID", "type": "text"},
        {"key": "provider_base_url", "label": "Primary Provider Base URL", "type": "text"},
        {
            "key": "provider_api_key",
            "label": "Primary Provider API Key",
            "type": "password",
            "sensitive": True,
        },
        {
            "key": "provider_auth",
            "label": "Primary Provider Auth",
            "type": "select",
            "options": OPENCLAW_PROVIDER_AUTH_OPTIONS,
        },
        {
            "key": "provider_api",
            "label": "Primary Provider API",
            "type": "select",
            "options": OPENCLAW_MODEL_API_OPTIONS,
        },
        {
            "key": "provider_models_json5",
            "label": "Primary Provider Models JSON5",
            "type": "textarea",
            "placeholder": '[\n  {\n    id: "kimi-k2.5",\n    name: "Kimi K2.5",\n    reasoning: true,\n    input: ["text", "image"],\n    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },\n    contextWindow: 128000,\n    maxTokens: 8192\n  }\n]',
        },
        {"key": "hooks_enabled", "label": "Hooks Enabled", "type": "boolean"},
        {"key": "hooks_path", "label": "Hooks Path", "type": "text"},
        {"key": "hooks_token", "label": "Hooks Token", "type": "password", "sensitive": True},
        {"key": "cron_enabled", "label": "Cron Enabled", "type": "boolean"},
        {"key": "cron_max_concurrent_runs", "label": "Cron Max Concurrent Runs", "type": "number"},
        {
            "key": "providers_json5",
            "label": "Models Providers JSON5",
            "type": "textarea",
            "placeholder": '{\n  moonshot: {\n    baseUrl: "https://api.moonshot.ai/v1",\n    apiKey: "${MOONSHOT_API_KEY}",\n    api: "openai-completions",\n    models: [{ id: "kimi-k2.5", name: "Kimi K2.5" }]\n  }\n}',
        },
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
        "sandbox": {"mode": "non-main", "workspaceAccess": "rw"},
        "session": {"dmScope": "main"},
        "hooks": {"enabled": False, "path": ".openclaw/hooks.js", "token": ""},
        "cron": {"enabled": False, "maxConcurrentRuns": 1},
        "models": {"mode": "merge", "providers": {}},
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


def normalize_openclaw_sandbox_config(values: Any) -> dict[str, Any]:
    sandbox = {"mode": "non-main", "workspaceAccess": "rw"}
    if isinstance(values, dict):
        sandbox = deep_merge(sandbox, values)
    mode = sandbox.get("mode")
    if mode in LEGACY_OPENCLAW_SANDBOX_MODES:
        sandbox = deep_merge(sandbox, LEGACY_OPENCLAW_SANDBOX_MODES[mode])
    if sandbox.get("workspaceAccess") in {None, ""}:
        sandbox["workspaceAccess"] = "rw"
    return sandbox


def normalize_openclaw_session_config(values: Any) -> dict[str, Any]:
    session = {"dmScope": "main"}
    if isinstance(values, dict):
        session = deep_merge(session, values)
    dm_scope = session.get("dmScope")
    if dm_scope in LEGACY_OPENCLAW_DM_SCOPES:
        session["dmScope"] = LEGACY_OPENCLAW_DM_SCOPES[dm_scope]
    return session


def normalize_openclaw_models_config(values: Any) -> dict[str, Any]:
    models = {"mode": "merge", "providers": {}}
    if isinstance(values, dict):
        models = deep_merge(models, values)
    if not isinstance(models.get("providers"), dict):
        models["providers"] = {}
    return models


def normalize_openclaw_config(values: dict[str, Any]) -> dict[str, Any]:
    normalized = deep_merge(default_openclaw_config_base(), values or {})
    normalized["sandbox"] = normalize_openclaw_sandbox_config(normalized.get("sandbox"))
    normalized["session"] = normalize_openclaw_session_config(normalized.get("session"))
    normalized["models"] = normalize_openclaw_models_config(normalized.get("models"))
    return normalized


def parse_openclaw_raw_json5(raw_json5: str) -> dict[str, Any]:
    try:
        parsed = json5.loads(raw_json5)
    except Exception as exc:
        raise ValueError(f"invalid openclaw json5: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("openclaw raw config must be a JSON object")
    return parsed


def parse_openclaw_providers_json5(raw_json5: str) -> dict[str, Any]:
    if not raw_json5.strip():
        return {}
    try:
        parsed = json5.loads(raw_json5)
    except Exception as exc:
        raise ValueError(f"invalid providers json5: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("models.providers must be a JSON object")
    return parsed


def parse_openclaw_provider_models_json5(raw_json5: str) -> list[dict[str, Any]]:
    if not raw_json5.strip():
        return []
    try:
        parsed = json5.loads(raw_json5)
    except Exception as exc:
        raise ValueError(f"invalid provider models json5: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError("provider models must be a JSON array")
    if any(not isinstance(item, dict) for item in parsed):
        raise ValueError("provider models entries must be JSON objects")
    return parsed


def mask_openclaw_providers(values: dict[str, Any]) -> dict[str, Any]:
    masked = copy.deepcopy(values if isinstance(values, dict) else {})
    for provider in masked.values():
        if not isinstance(provider, dict):
            continue
        if provider.get("apiKey"):
            provider["apiKey"] = MASKED_VALUE
        headers = provider.get("headers")
        if isinstance(headers, dict):
            for key, value in list(headers.items()):
                if isinstance(value, str) and value:
                    headers[key] = MASKED_VALUE
    return masked


def restore_masked_openclaw_providers(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    restored = copy.deepcopy(incoming if isinstance(incoming, dict) else {})
    current = existing if isinstance(existing, dict) else {}
    for provider_id, provider in restored.items():
        if not isinstance(provider, dict):
            continue
        existing_provider = current.get(provider_id)
        if not isinstance(existing_provider, dict):
            continue
        if provider.get("apiKey") == MASKED_VALUE and existing_provider.get("apiKey"):
            provider["apiKey"] = existing_provider["apiKey"]
        headers = provider.get("headers")
        existing_headers = existing_provider.get("headers")
        if not isinstance(headers, dict) or not isinstance(existing_headers, dict):
            continue
        for header_key, header_value in list(headers.items()):
            if header_value == MASKED_VALUE and header_key in existing_headers:
                headers[header_key] = existing_headers[header_key]
    return restored


def mask_openclaw_config(values: dict[str, Any]) -> dict[str, Any]:
    masked = copy.deepcopy(normalize_openclaw_config(values or {}))
    hooks = masked.get("hooks")
    if isinstance(hooks, dict) and hooks.get("token"):
        hooks["token"] = MASKED_VALUE
    providers = get_nested_value(masked, ["models", "providers"], {})
    set_nested_value(masked, ["models", "providers"], mask_openclaw_providers(providers))
    return masked


def restore_masked_openclaw_config(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    restored = copy.deepcopy(incoming if isinstance(incoming, dict) else {})
    current = normalize_openclaw_config(existing or {})
    hooks = restored.get("hooks")
    current_hooks = current.get("hooks")
    if isinstance(hooks, dict) and isinstance(current_hooks, dict):
        if hooks.get("token") == MASKED_VALUE and current_hooks.get("token"):
            hooks["token"] = current_hooks["token"]
    incoming_providers = get_nested_value(restored, ["models", "providers"], {})
    current_providers = get_nested_value(current, ["models", "providers"], {})
    if isinstance(incoming_providers, dict):
        set_nested_value(
            restored,
            ["models", "providers"],
            restore_masked_openclaw_providers(current_providers, incoming_providers),
        )
    return restored


def select_openclaw_provider(values: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    providers = get_nested_value(values, ["models", "providers"], {})
    if not isinstance(providers, dict) or not providers:
        return "", None
    primary_model = get_nested_value(values, ["model", "primary"], "")
    if isinstance(primary_model, str) and "/" in primary_model:
        provider_id = primary_model.split("/", 1)[0]
        provider = providers.get(provider_id)
        if isinstance(provider, dict):
            return provider_id, provider
    provider_id = sorted(providers.keys())[0]
    provider = providers.get(provider_id)
    return provider_id, provider if isinstance(provider, dict) else None


def extract_openclaw_structured_values(values: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_openclaw_config(values or {})
    fallbacks = get_nested_value(normalized, ["model", "fallbacks"], [])
    fallback_text = (
        f"{OPENCLAW_FALLBACK_SEPARATOR} ".join(str(item) for item in fallbacks)
        if isinstance(fallbacks, list)
        else ""
    )
    provider_id, provider = select_openclaw_provider(normalized)
    masked_providers = mask_openclaw_providers(get_nested_value(normalized, ["models", "providers"], {}))
    return {
        "primary_model": get_nested_value(normalized, ["model", "primary"], ""),
        "fallback_models": fallback_text,
        "sandbox_mode": get_nested_value(normalized, ["sandbox", "mode"], "non-main"),
        "sandbox_workspace_access": get_nested_value(normalized, ["sandbox", "workspaceAccess"], "rw"),
        "session_dm_scope": get_nested_value(normalized, ["session", "dmScope"], "main"),
        "models_mode": get_nested_value(normalized, ["models", "mode"], "merge"),
        "provider_id": provider_id,
        "provider_base_url": provider.get("baseUrl", "") if provider else "",
        "provider_api_key": MASKED_VALUE if provider and provider.get("apiKey") else "",
        "provider_auth": provider.get("auth", "") if provider else "",
        "provider_api": provider.get("api", "") if provider else "",
        "provider_models_json5": json.dumps(provider.get("models", []), indent=2, ensure_ascii=False) if provider else "",
        "hooks_enabled": get_nested_value(normalized, ["hooks", "enabled"], False),
        "hooks_path": get_nested_value(normalized, ["hooks", "path"], ".openclaw/hooks.js"),
        "hooks_token": MASKED_VALUE if get_nested_value(normalized, ["hooks", "token"], "") else "",
        "cron_enabled": get_nested_value(normalized, ["cron", "enabled"], False),
        "cron_max_concurrent_runs": get_nested_value(normalized, ["cron", "maxConcurrentRuns"], 1),
        "providers_json5": json.dumps(masked_providers, indent=2, ensure_ascii=False),
    }


def merge_explicit_openclaw_provider(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    provider_id = incoming.get("provider_id")
    provider_fields_present = any(
        key in incoming
        for key in ["provider_base_url", "provider_api_key", "provider_auth", "provider_api", "provider_models_json5"]
    )
    if provider_id is None and not provider_fields_present:
        return existing
    if not isinstance(provider_id, str):
        raise ValueError("provider_id must be a string")
    provider_id = provider_id.strip()
    if not provider_id:
        if provider_fields_present:
            raise ValueError("provider_id is required when editing primary provider settings")
        return existing

    providers = copy.deepcopy(get_nested_value(existing, ["models", "providers"], {}))
    current_provider = providers.get(provider_id, {})
    if not isinstance(current_provider, dict):
        current_provider = {}
    provider = copy.deepcopy(current_provider)

    if "provider_base_url" in incoming:
        base_url = incoming["provider_base_url"]
        if not isinstance(base_url, str):
            raise ValueError("provider_base_url must be a string")
        if base_url.strip():
            provider["baseUrl"] = base_url
        else:
            provider.pop("baseUrl", None)
    if "provider_api_key" in incoming:
        api_key = incoming["provider_api_key"]
        if not isinstance(api_key, str):
            raise ValueError("provider_api_key must be a string")
        if api_key != MASKED_VALUE:
            provider["apiKey"] = api_key
    if "provider_auth" in incoming:
        auth = incoming["provider_auth"]
        if not isinstance(auth, str):
            raise ValueError("provider_auth must be a string")
        if auth.strip():
            provider["auth"] = auth
        else:
            provider.pop("auth", None)
    if "provider_api" in incoming:
        api = incoming["provider_api"]
        if not isinstance(api, str):
            raise ValueError("provider_api must be a string")
        if api.strip():
            provider["api"] = api
        else:
            provider.pop("api", None)
    if "provider_models_json5" in incoming:
        raw_models = incoming["provider_models_json5"]
        if not isinstance(raw_models, str):
            raise ValueError("provider_models_json5 must be a string")
        provider["models"] = parse_openclaw_provider_models_json5(raw_models)

    providers[provider_id] = provider
    set_nested_value(existing, ["models", "providers"], providers)
    return existing


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
    if "sandbox_workspace_access" in incoming:
        set_nested_value(merged, ["sandbox", "workspaceAccess"], incoming["sandbox_workspace_access"])
    if "session_dm_scope" in incoming:
        set_nested_value(merged, ["session", "dmScope"], incoming["session_dm_scope"])
    if "models_mode" in incoming:
        set_nested_value(merged, ["models", "mode"], incoming["models_mode"])
    if "hooks_enabled" in incoming:
        set_nested_value(merged, ["hooks", "enabled"], incoming["hooks_enabled"])
    if "hooks_path" in incoming:
        set_nested_value(merged, ["hooks", "path"], incoming["hooks_path"])
    if "hooks_token" in incoming and incoming["hooks_token"] != MASKED_VALUE:
        set_nested_value(merged, ["hooks", "token"], incoming["hooks_token"])
    if "cron_enabled" in incoming:
        set_nested_value(merged, ["cron", "enabled"], incoming["cron_enabled"])
    if "cron_max_concurrent_runs" in incoming:
        set_nested_value(merged, ["cron", "maxConcurrentRuns"], incoming["cron_max_concurrent_runs"])
    if "providers_json5" in incoming:
        raw_providers = incoming["providers_json5"]
        if not isinstance(raw_providers, str):
            raise ValueError("providers_json5 must be a string")
        providers = parse_openclaw_providers_json5(raw_providers)
        existing_providers = get_nested_value(merged, ["models", "providers"], {})
        set_nested_value(merged, ["models", "providers"], restore_masked_openclaw_providers(existing_providers, providers))
    merged = merge_explicit_openclaw_provider(merged, incoming)
    return normalize_openclaw_config(merged)


def validate_openclaw_config(values: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_openclaw_config(values or {})
    checks = extract_openclaw_structured_values(normalized)
    if not isinstance(checks["primary_model"], str):
        raise ValueError("model.primary must be string")
    if not isinstance(checks["fallback_models"], str):
        raise ValueError("model.fallbacks must be serializable")
    if checks["sandbox_mode"] not in OPENCLAW_SANDBOX_MODE_OPTIONS:
        raise ValueError("sandbox.mode is not supported")
    if checks["sandbox_workspace_access"] not in OPENCLAW_SANDBOX_WORKSPACE_ACCESS_OPTIONS:
        raise ValueError("sandbox.workspaceAccess is not supported")
    if checks["session_dm_scope"] not in OPENCLAW_SESSION_DM_SCOPE_OPTIONS:
        raise ValueError("session.dmScope is not supported")
    if not isinstance(checks["hooks_enabled"], bool):
        raise ValueError("hooks.enabled must be boolean")
    if not isinstance(checks["hooks_path"], str):
        raise ValueError("hooks.path must be string")
    if not isinstance(get_nested_value(normalized, ["hooks", "token"], ""), str):
        raise ValueError("hooks.token must be string")
    if not isinstance(checks["cron_enabled"], bool):
        raise ValueError("cron.enabled must be boolean")
    if not isinstance(checks["cron_max_concurrent_runs"], int):
        raise ValueError("cron.maxConcurrentRuns must be integer")
    models = normalized.get("models")
    if models is not None:
        if not isinstance(models, dict):
            raise ValueError("models must be object")
        providers = models.get("providers")
        if providers is not None and not isinstance(providers, dict):
            raise ValueError("models.providers must be object")
        mode = models.get("mode")
        if mode is not None and mode not in {"merge", "replace"}:
            raise ValueError("models.mode is not supported")
        if isinstance(providers, dict):
            for provider_id, provider in providers.items():
                if not isinstance(provider_id, str) or not provider_id.strip():
                    raise ValueError("models.providers keys must be non-empty strings")
                if not isinstance(provider, dict):
                    raise ValueError(f"models.providers.{provider_id} must be object")
                base_url = provider.get("baseUrl")
                if base_url is not None and not isinstance(base_url, str):
                    raise ValueError(f"models.providers.{provider_id}.baseUrl must be string")
                api_key = provider.get("apiKey")
                if api_key is not None and not isinstance(api_key, str):
                    raise ValueError(f"models.providers.{provider_id}.apiKey must be string")
                auth = provider.get("auth")
                if auth is not None and auth not in OPENCLAW_PROVIDER_AUTH_OPTIONS:
                    raise ValueError(f"models.providers.{provider_id}.auth is not supported")
                api = provider.get("api")
                if api is not None and api not in OPENCLAW_MODEL_API_OPTIONS:
                    raise ValueError(f"models.providers.{provider_id}.api is not supported")
                provider_models = provider.get("models")
                if provider_models is not None and not isinstance(provider_models, list):
                    raise ValueError(f"models.providers.{provider_id}.models must be array")
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
            "models": raw_values.get("models", {}),
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
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return datetime.now(timezone.utc)


def mask_openclaw_channel_config(values: dict[str, Any]) -> dict[str, Any]:
    masked = copy.deepcopy(values or default_openclaw_channel_config())
    if masked.get("app_secret"):
        masked["app_secret"] = MASKED_VALUE
    return masked


def build_openclaw_gateway_config(port: int) -> dict[str, Any]:
    return {
        "mode": "local",
        "port": port,
    }


def render_openclaw_workspace_payload(openclaw_config: dict[str, Any]) -> dict[str, Any]:
    validated = validate_openclaw_config(openclaw_config)
    return {
        "gateway": build_openclaw_gateway_config(7331),
        "models": copy.deepcopy(validated.get("models", {})),
        "session": copy.deepcopy(validated.get("session", {})),
        "hooks": copy.deepcopy(validated.get("hooks", {})),
        "cron": copy.deepcopy(validated.get("cron", {})),
        "agents": {
            "defaults": {
                "workspace": "~/.openclaw/workspace",
                "model": copy.deepcopy(validated.get("model", {})),
                "sandbox": copy.deepcopy(validated.get("sandbox", {})),
            }
        },
    }


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
    shared_config = default_openclaw_config()

    for item in sorted(workspaces, key=lambda current: current["workspace"].id):
        workspace = item["workspace"]
        agent_config = validate_openclaw_config(item["openclaw_config"])
        channel_config = validate_openclaw_channel_config(item["openclaw_channel"])
        binding_config = validate_openclaw_binding_config(item["openclaw_binding"])
        route = build_openclaw_route(channel_config, binding_config, workspace.id)
        agent_id = route["agent_id"]

        shared_config["models"] = deep_merge(shared_config.get("models", {}), copy.deepcopy(agent_config.get("models", {})))
        shared_config["session"] = deep_merge(
            shared_config.get("session", {}),
            copy.deepcopy(agent_config.get("session", {})),
        )
        shared_config["hooks"] = deep_merge(shared_config.get("hooks", {}), copy.deepcopy(agent_config.get("hooks", {})))
        shared_config["cron"] = deep_merge(shared_config.get("cron", {}), copy.deepcopy(agent_config.get("cron", {})))

        agents.append(
            {
                "id": agent_id,
                "name": workspace.name,
                "workspace": item["workspace_path"],
                "model": copy.deepcopy(agent_config.get("model", {})),
                "sandbox": copy.deepcopy(agent_config.get("sandbox", {})),
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
                    "agentId": agent_id,
                    "match": {
                        "channel": route["channel"],
                        "accountId": route["account_id"],
                    },
                }
            )

    return {
        "gateway": build_openclaw_gateway_config(settings.openclaw_gateway_port),
        "models": copy.deepcopy(shared_config.get("models", {})),
        "session": copy.deepcopy(shared_config.get("session", {})),
        "hooks": copy.deepcopy(shared_config.get("hooks", {})),
        "cron": copy.deepcopy(shared_config.get("cron", {})),
        "channels": {"feishu": {"accounts": accounts}},
        "agents": {"list": agents},
        "bindings": bindings,
    }
