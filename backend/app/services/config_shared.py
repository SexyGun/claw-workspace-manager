from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


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


def string_value(value: Any) -> str:
    return value if isinstance(value, str) else ""


def section_dict(values: dict[str, Any], key: str) -> dict[str, Any]:
    section = values.get(key, {})
    return section if isinstance(section, dict) else {}


def write_nanobot_config(file_path: Path, payload: dict[str, Any]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return datetime.now(timezone.utc)


def write_runtime_env(file_path: Path, payload: dict[str, str | int]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in payload.items()]
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return datetime.now(timezone.utc)


def write_openclaw_aggregate_config(file_path: Path, payload: dict[str, Any]) -> datetime:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return datetime.now(timezone.utc)
