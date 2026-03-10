from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any

from app import models
from app.config import Settings
from app.constants import RUNTIME_STATE_ERROR, RUNTIME_STATE_RUNNING
from app.services import config_renderer, workspace as workspace_service


def _runtime_attr(runtime: Any, key: str) -> Any:
    if runtime is None:
        return None
    return getattr(runtime, key, None)


def _base_instance_config(workspace: models.Workspace, settings: Settings) -> dict[str, Any]:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    source_config_path = local_path / ".nanobot" / "config.json"
    return config_renderer.load_nanobot_instance_config(source_config_path)


def _enabled_nanobot_channels(channel_config: dict[str, Any]) -> list[str]:
    normalized, _ = config_renderer.normalize_channel_config(channel_config)
    labels: list[str] = []
    if normalized["feishu"]["enabled"]:
        labels.append("Feishu")
    if normalized["dingtalk"]["enabled"]:
        labels.append("DingTalk")
    if normalized["qq"]["enabled"]:
        labels.append("QQ")
    return labels


def _nanobot_channel_complete(channel_config: dict[str, Any]) -> bool:
    normalized, _ = config_renderer.normalize_channel_config(channel_config)
    return any(
        [
            bool(
                normalized["feishu"]["enabled"]
                and normalized["feishu"]["app_id"].strip()
                and normalized["feishu"]["app_secret"].strip()
            ),
            bool(
                normalized["dingtalk"]["enabled"]
                and normalized["dingtalk"]["client_id"].strip()
                and normalized["dingtalk"]["client_secret"].strip()
            ),
            bool(
                normalized["qq"]["enabled"]
                and normalized["qq"]["app_id"].strip()
                and normalized["qq"]["secret"].strip()
            ),
        ]
    )


def _nanobot_provider_complete(base_config: dict[str, Any]) -> bool:
    agent = config_renderer.extract_agent_defaults_config(base_config)
    provider_key = agent.get("provider", "auto")
    if provider_key == "auto":
        return True
    providers = config_renderer.extract_provider_config(base_config)
    section = providers.get(provider_key, {})
    return any(isinstance(value, str) and value.strip() for value in section.values())


def _openclaw_channel_complete(channel_config: dict[str, Any]) -> bool:
    merged = config_renderer.merge_openclaw_channel_config({}, channel_config or {})
    return bool(
        merged["enabled"]
        and merged["account_id"].strip()
        and merged["app_id"].strip()
        and merged["app_secret"].strip()
    )


def _latest_activity(
    workspace: models.Workspace,
    *,
    runtime: Any = None,
    shared_runtime: Any = None,
) -> datetime | None:
    candidates = [
        workspace.created_at,
        _runtime_attr(runtime, "started_at"),
        _runtime_attr(runtime, "stopped_at"),
        _runtime_attr(shared_runtime, "started_at"),
        _runtime_attr(shared_runtime, "stopped_at"),
        workspace.config.nanobot_rendered_at if workspace.config else None,
        workspace.config.gateway_rendered_at if workspace.config else None,
        workspace.config.openclaw_rendered_at if workspace.config else None,
    ]
    existing = [candidate for candidate in candidates if candidate is not None]
    return max(existing) if existing else None


def _config_complete(workspace: models.Workspace, settings: Settings) -> tuple[bool, dict[str, Any]]:
    if workspace.workspace_type == "base":
        base_config = _base_instance_config(workspace, settings)
        agent = config_renderer.extract_agent_defaults_config(base_config)
        complete = bool(agent.get("model", "").strip()) and _nanobot_provider_complete(base_config) and _nanobot_channel_complete(
            workspace.config.channel_config_json or {}
        )
        return complete, {
            "base_config": base_config,
            "agent": agent,
            "channels": _enabled_nanobot_channels(workspace.config.channel_config_json or {}),
        }

    openclaw_config = workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
    structured = config_renderer.extract_openclaw_structured_values(openclaw_config)
    complete = (
        bool(structured.get("primary_model", "").strip())
        and _openclaw_channel_complete(workspace.config.openclaw_channel_json or {})
        and bool(str(structured.get("sandbox_mode", "")).strip())
        and bool(str(structured.get("session_dm_scope", "")).strip())
    )
    return complete, {"structured": structured}


def compute_setup_progress(workspace: models.Workspace, settings: Settings, activation_state: str | None) -> dict[str, Any]:
    completed_steps: list[str] = ["已选择工作区类型"]
    missing_items: list[str] = []

    if workspace.workspace_type == "base":
        base_config = _base_instance_config(workspace, settings)
        agent = config_renderer.extract_agent_defaults_config(base_config)
        if agent.get("model", "").strip():
            completed_steps.append("已配置模型")
        else:
            missing_items.append("默认模型")

        if _nanobot_provider_complete(base_config):
            completed_steps.append("已配置模型服务")
        else:
            missing_items.append("Provider 凭据")

        if _nanobot_channel_complete(workspace.config.channel_config_json or {}):
            completed_steps.append("已绑定渠道")
        else:
            missing_items.append("渠道账号绑定")

        completed_steps.append("已设置运行方式")
    else:
        structured = config_renderer.extract_openclaw_structured_values(
            workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
        )
        if str(structured.get("primary_model", "")).strip():
            completed_steps.append("已配置模型")
        else:
            missing_items.append("默认模型")

        if _openclaw_channel_complete(workspace.config.openclaw_channel_json or {}):
            completed_steps.append("已绑定渠道")
        else:
            missing_items.append("飞书账号绑定")

        if str(structured.get("sandbox_mode", "")).strip() and str(structured.get("session_dm_scope", "")).strip():
            completed_steps.append("已设置运行方式")
        else:
            missing_items.append("运行方式")

        completed_steps.append("已选择工作区类型")

    if activation_state == "active":
        completed_steps.append("已启动工作区")
    else:
        missing_items.append("启动服务")

    # The flow is fixed at five steps; keep the percent stable and user-facing.
    unique_completed = []
    for item in completed_steps:
        if item not in unique_completed:
            unique_completed.append(item)
    completion_percent = min(100, int(len(unique_completed) / 5 * 100))
    return {
        "completion_percent": completion_percent,
        "completed_steps": unique_completed,
        "missing_items": missing_items,
    }


def compute_dashboard_state(
    workspace: models.Workspace,
    settings: Settings,
    activation_state: str | None,
    *,
    runtime: Any = None,
    shared_runtime: Any = None,
) -> str:
    config_complete, _ = _config_complete(workspace, settings)
    runtime_error = _runtime_attr(runtime, "state") == RUNTIME_STATE_ERROR or bool(_runtime_attr(runtime, "last_error"))
    shared_error = _runtime_attr(shared_runtime, "state") == RUNTIME_STATE_ERROR or bool(_runtime_attr(shared_runtime, "last_error"))

    if workspace.workspace_type == "openclaw":
        if shared_error:
            return "error"
        if activation_state == "active" and _runtime_attr(shared_runtime, "state") == RUNTIME_STATE_RUNNING:
            return "running"
        if not config_complete:
            return "needs_setup"
        return "stopped"

    if runtime_error:
        return "error"
    if activation_state == "active":
        return "running"
    if not config_complete:
        return "needs_setup"
    return "stopped"


def compute_workspace_list_item(
    workspace: models.Workspace,
    settings: Settings,
    activation_state: str | None,
    *,
    runtime: Any = None,
    shared_runtime: Any = None,
) -> dict[str, Any]:
    setup_progress = compute_setup_progress(workspace, settings, activation_state)
    dashboard_state = compute_dashboard_state(
        workspace,
        settings,
        activation_state,
        runtime=runtime,
        shared_runtime=shared_runtime,
    )

    if workspace.workspace_type == "base":
        base_config = _base_instance_config(workspace, settings)
        agent = config_renderer.extract_agent_defaults_config(base_config)
        channel_labels = _enabled_nanobot_channels(workspace.config.channel_config_json or {})
        model_summary = agent.get("model", "").strip() or "未配置"
        channel_summary = " / ".join(channel_labels) if channel_labels else "未配置"
    else:
        structured = config_renderer.extract_openclaw_structured_values(
            workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
        )
        channel_config = config_renderer.merge_openclaw_channel_config({}, workspace.config.openclaw_channel_json or {})
        channel_summary = f"Feishu · {channel_config['account_id']}" if channel_config["account_id"].strip() else "未配置"
        model_summary = str(structured.get("primary_model", "")).strip() or "未配置"

    return {
        "dashboard_state": dashboard_state,
        "channel_summary": channel_summary,
        "model_summary": model_summary,
        "completion_percent": setup_progress["completion_percent"],
        "last_activity_at": _latest_activity(workspace, runtime=runtime, shared_runtime=shared_runtime),
    }


def compute_workspace_summary_metadata(
    workspace: models.Workspace,
    settings: Settings,
    activation_state: str | None,
    *,
    runtime: Any = None,
    shared_runtime: Any = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    list_item = compute_workspace_list_item(
        workspace,
        settings,
        activation_state,
        runtime=runtime,
        shared_runtime=shared_runtime,
    )
    setup_progress = compute_setup_progress(workspace, settings, activation_state)
    config_complete, extracted = _config_complete(workspace, settings)

    if workspace.workspace_type == "base":
        last_error = _runtime_attr(runtime, "last_error")
        service_state = _runtime_attr(runtime, "state") or "stopped"
        route_state = "not_applicable"
        model_state = "configured" if extracted["agent"].get("model", "").strip() else "missing"
        entry_label = "网关端口"
        entry_value = str(workspace.runtime.listen_port) if workspace.runtime and workspace.runtime.listen_port else None
        recommended_actions = []
        if not extracted["agent"].get("model", "").strip():
            recommended_actions.append("完善模型配置")
        if not _nanobot_channel_complete(workspace.config.channel_config_json or {}):
            recommended_actions.append("绑定渠道")
        if activation_state != "active":
            recommended_actions.append("启动工作区")
        if last_error:
            recommended_actions.insert(0, "查看诊断")
    else:
        last_error = _runtime_attr(shared_runtime, "last_error")
        service_state = _runtime_attr(shared_runtime, "state") or "stopped"
        route_state = "connected" if activation_state == "active" else "disconnected"
        model_state = "configured" if str(extracted["structured"].get("primary_model", "")).strip() else "missing"
        entry_label = "共享端口"
        entry_value = str(settings.openclaw_gateway_port)
        recommended_actions = []
        if not str(extracted["structured"].get("primary_model", "")).strip():
            recommended_actions.append("完善模型配置")
        if not _openclaw_channel_complete(workspace.config.openclaw_channel_json or {}):
            recommended_actions.append("绑定飞书账号")
        if activation_state != "active":
            recommended_actions.append("启动工作区")
        if activation_state == "active" and service_state != "running":
            recommended_actions.insert(0, "启动 OpenClaw 共享服务")
        if last_error:
            recommended_actions.insert(0, "查看诊断")

    diagnostics_summary = {
        "latest_error": last_error,
        "has_logs": True,
        "available_checks": ["config", "startup", "logs"],
    }

    return {
        "overview": {
            "dashboard_state": list_item["dashboard_state"],
            "channel_summary": list_item["channel_summary"],
            "model_summary": list_item["model_summary"],
            "entry_label": entry_label,
            "entry_value": entry_value,
            "last_activity_at": list_item["last_activity_at"],
        },
        "health": {
            "service_state": service_state,
            "route_state": route_state,
            "model_state": model_state,
            "config_state": "complete" if config_complete else "incomplete",
            "last_error": last_error,
            "started_at": _runtime_attr(runtime, "started_at") or _runtime_attr(shared_runtime, "started_at"),
            "checked_at": now,
        },
        "setup_progress": setup_progress,
        "recommended_actions": recommended_actions[:4],
        "diagnostics_summary": diagnostics_summary,
    }


def build_diagnostic_checks(
    workspace: models.Workspace,
    settings: Settings,
    activation_state: str | None,
    *,
    runtime: Any = None,
    shared_runtime: Any = None,
) -> list[dict[str, Any]]:
    local_path = workspace_service.local_path_from_host_path(settings, workspace.host_path)
    checks: list[dict[str, Any]] = []

    if workspace.workspace_type == "base":
        base_config = _base_instance_config(workspace, settings)
        agent = config_renderer.extract_agent_defaults_config(base_config)
        runtime_root = settings.runtime_state_root / "nanobot" / str(workspace.id)
        checks.extend(
            [
                {
                    "code": "model_configured",
                    "label": "模型配置",
                    "status": "ok" if agent.get("model", "").strip() else "warn",
                    "message": "已设置默认模型" if agent.get("model", "").strip() else "请先设置默认模型",
                    "suggested_action": None if agent.get("model", "").strip() else "打开配置页完善模型设置",
                },
                {
                    "code": "provider_ready",
                    "label": "Provider 准备情况",
                    "status": "ok" if _nanobot_provider_complete(base_config) else "warn",
                    "message": "Provider 配置已就绪" if _nanobot_provider_complete(base_config) else "所选 Provider 凭据未配置完整",
                    "suggested_action": None if _nanobot_provider_complete(base_config) else "补齐 Provider 凭据后保存",
                },
                {
                    "code": "channel_ready",
                    "label": "渠道绑定",
                    "status": "ok" if _nanobot_channel_complete(workspace.config.channel_config_json or {}) else "warn",
                    "message": "至少一个渠道已启用" if _nanobot_channel_complete(workspace.config.channel_config_json or {}) else "尚未绑定可用渠道",
                    "suggested_action": None if _nanobot_channel_complete(workspace.config.channel_config_json or {}) else "配置 Feishu、DingTalk 或 QQ 账号",
                },
                {
                    "code": "runtime_artifacts",
                    "label": "运行文件",
                    "status": "ok"
                    if (local_path / ".nanobot" / "config.json").exists() and (runtime_root / "config.json").exists()
                    else "error",
                    "message": "运行配置文件已生成"
                    if (local_path / ".nanobot" / "config.json").exists() and (runtime_root / "config.json").exists()
                    else "运行配置文件缺失",
                    "suggested_action": None
                    if (local_path / ".nanobot" / "config.json").exists() and (runtime_root / "config.json").exists()
                    else "重新保存配置并重试",
                },
                {
                    "code": "runtime_service",
                    "label": "工作区服务",
                    "status": "ok"
                    if _runtime_attr(runtime, "state") == "running"
                    else "error"
                    if _runtime_attr(runtime, "state") == "error"
                    else "warn",
                    "message": "工作区服务运行正常"
                    if _runtime_attr(runtime, "state") == "running"
                    else _runtime_attr(runtime, "last_error") or "工作区服务尚未启动",
                    "suggested_action": None
                    if _runtime_attr(runtime, "state") == "running"
                    else "尝试重新启动工作区并查看日志",
                },
            ]
        )
        return checks

    structured = config_renderer.extract_openclaw_structured_values(
        workspace.config.openclaw_config_json or config_renderer.default_openclaw_config()
    )
    aggregate_path = settings.runtime_state_root / "openclaw" / "openclaw.json"
    checks.extend(
        [
            {
                "code": "model_configured",
                "label": "模型配置",
                "status": "ok" if str(structured.get("primary_model", "")).strip() else "warn",
                "message": "已设置默认模型" if str(structured.get("primary_model", "")).strip() else "请先设置默认模型",
                "suggested_action": None if str(structured.get("primary_model", "")).strip() else "打开配置页完善模型设置",
            },
            {
                "code": "channel_ready",
                "label": "渠道绑定",
                "status": "ok" if _openclaw_channel_complete(workspace.config.openclaw_channel_json or {}) else "warn",
                "message": "飞书账号配置已完成" if _openclaw_channel_complete(workspace.config.openclaw_channel_json or {}) else "飞书账号配置未完成",
                "suggested_action": None if _openclaw_channel_complete(workspace.config.openclaw_channel_json or {}) else "补齐飞书 App ID、Secret 和账号 ID",
            },
            {
                "code": "route_enabled",
                "label": "Workspace 路由",
                "status": "ok" if activation_state == "active" else "warn",
                "message": "当前路由已启用" if activation_state == "active" else "当前路由尚未启用",
                "suggested_action": None if activation_state == "active" else "保存后点击启动工作区",
            },
            {
                "code": "workspace_artifacts",
                "label": "运行文件",
                "status": "ok"
                if (local_path / ".openclaw" / "openclaw.json").exists()
                and (local_path / ".openclaw" / "channel.json").exists()
                and aggregate_path.exists()
                else "error",
                "message": "Workspace 与聚合配置均已生成"
                if (local_path / ".openclaw" / "openclaw.json").exists()
                and (local_path / ".openclaw" / "channel.json").exists()
                and aggregate_path.exists()
                else "OpenClaw 配置文件缺失",
                "suggested_action": None
                if (local_path / ".openclaw" / "openclaw.json").exists()
                and (local_path / ".openclaw" / "channel.json").exists()
                and aggregate_path.exists()
                else "重新保存配置并重试",
            },
            {
                "code": "shared_service",
                "label": "共享 OpenClaw 服务",
                "status": "ok"
                if _runtime_attr(shared_runtime, "state") == "running"
                else "error"
                if _runtime_attr(shared_runtime, "state") == "error"
                else "warn",
                "message": "共享服务运行正常"
                if _runtime_attr(shared_runtime, "state") == "running"
                else _runtime_attr(shared_runtime, "last_error") or "共享服务尚未启动",
                "suggested_action": None
                if _runtime_attr(shared_runtime, "state") == "running"
                else "请由管理员启动或重启共享 OpenClaw 服务",
            },
        ]
    )
    return checks


def _journal_entries(settings: Settings, unit_name: str, limit: int) -> list[dict[str, Any]]:
    command: list[str] = []
    if settings.systemctl_use_sudo:
        command.extend(settings.sudo_command_argv)
    command.extend(["journalctl", "-u", unit_name, "-n", str(limit), "--no-pager", "-o", "short-iso"])
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    entries: list[dict[str, Any]] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        timestamp = None
        message = line
        first_space = line.find(" ")
        if first_space > 0:
            possible_timestamp = line[:first_space]
            try:
                timestamp = datetime.fromisoformat(possible_timestamp.replace("Z", "+00:00"))
                message = line[first_space + 1 :].strip()
            except ValueError:
                timestamp = None
        lowered = message.lower()
        level = "error" if "error" in lowered or "failed" in lowered else "warning" if "warn" in lowered else "info"
        entries.append({"timestamp": timestamp, "level": level, "message": message})
    return entries


def build_diagnostic_logs(
    workspace: models.Workspace,
    settings: Settings,
    activation_state: str | None,
    *,
    runtime: Any = None,
    shared_runtime: Any = None,
    limit: int = 50,
) -> dict[str, Any]:
    if workspace.workspace_type == "base":
        unit_name = _runtime_attr(runtime, "unit_name")
        source = "workspace-runtime"
    else:
        unit_name = _runtime_attr(shared_runtime, "unit_name") or settings.openclaw_shared_unit
        source = "openclaw-shared"

    entries = _journal_entries(settings, unit_name, limit) if unit_name else []
    if entries:
        return {"source": source, "unit_name": unit_name, "entries": entries}

    fallback_entries: list[dict[str, Any]] = []
    rendered_at = workspace.config.nanobot_rendered_at if workspace.workspace_type == "base" else workspace.config.openclaw_rendered_at
    if rendered_at is not None:
        fallback_entries.append({"timestamp": rendered_at, "level": "info", "message": "配置文件已写入运行目录"})

    target_runtime = runtime if workspace.workspace_type == "base" else shared_runtime
    if _runtime_attr(target_runtime, "started_at") is not None:
        fallback_entries.append(
            {"timestamp": _runtime_attr(target_runtime, "started_at"), "level": "info", "message": "服务最近一次启动成功"}
        )
    if _runtime_attr(target_runtime, "stopped_at") is not None:
        fallback_entries.append(
            {"timestamp": _runtime_attr(target_runtime, "stopped_at"), "level": "warning", "message": "服务最近一次已停止"}
        )
    if _runtime_attr(target_runtime, "last_error") is not None:
        fallback_entries.append(
            {"timestamp": None, "level": "error", "message": _runtime_attr(target_runtime, "last_error")}
        )

    if workspace.workspace_type == "openclaw":
        fallback_entries.append(
            {
                "timestamp": None,
                "level": "info" if activation_state == "active" else "warning",
                "message": "Workspace 路由已启用" if activation_state == "active" else "Workspace 路由尚未启用",
            }
        )

    if not fallback_entries:
        fallback_entries.append({"timestamp": None, "level": "info", "message": "暂无运行日志，当前显示的是状态事件摘要"})

    return {"source": source, "unit_name": unit_name, "entries": fallback_entries[:limit]}
