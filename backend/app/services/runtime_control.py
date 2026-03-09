from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import subprocess
from typing import Sequence

from app.config import Settings
from app.constants import (
    RUNTIME_CONTROLLER_NONE,
    RUNTIME_CONTROLLER_SYSTEMD,
    RUNTIME_STATE_ERROR,
    RUNTIME_STATE_RUNNING,
    RUNTIME_STATE_STARTING,
    RUNTIME_STATE_STOPPED,
    RUNTIME_STATE_STOPPING,
)


@dataclass
class RuntimeStatus:
    state: str
    scope: str
    controller_kind: str
    unit_name: str | None = None
    process_id: int | None = None
    listen_port: int | None = None
    last_error: str | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    needs_restart: bool = False


@dataclass
class SystemdUnitStatus:
    unit_name: str
    state: str
    process_id: int | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None


class RuntimeControlError(RuntimeError):
    pass


class SystemdController:
    def __init__(self, settings: Settings):
        self.settings = settings

    def start(self, unit_name: str) -> SystemdUnitStatus:
        self._run_systemctl(["start", unit_name])
        return self.status(unit_name)

    def stop(self, unit_name: str) -> SystemdUnitStatus:
        self._run_systemctl(["stop", unit_name])
        return self.status(unit_name)

    def restart(self, unit_name: str) -> SystemdUnitStatus:
        self._run_systemctl(["restart", unit_name])
        return self.status(unit_name)

    def reload(self, unit_name: str) -> SystemdUnitStatus:
        self._run_systemctl(["reload", unit_name])
        return self.status(unit_name)

    def status(self, unit_name: str) -> SystemdUnitStatus:
        output = self._run_systemctl(
            [
                "show",
                unit_name,
                "--property=ActiveState",
                "--property=MainPID",
                "--property=ActiveEnterTimestampUSec",
                "--property=InactiveEnterTimestampUSec",
            ]
        )
        properties = self._parse_show_output(output)
        pid = self._parse_pid(properties.get("MainPID", "0"))
        return SystemdUnitStatus(
            unit_name=unit_name,
            state=self._map_active_state(properties.get("ActiveState", "inactive")),
            process_id=pid,
            started_at=self._parse_usec_timestamp(properties.get("ActiveEnterTimestampUSec", "0")),
            stopped_at=self._parse_usec_timestamp(properties.get("InactiveEnterTimestampUSec", "0")),
        )

    def _run_systemctl(self, args: Sequence[str]) -> str:
        cmd: list[str] = []
        if self.settings.systemctl_use_sudo:
            cmd.extend(self.settings.sudo_command_argv)
        cmd.extend(self.settings.systemctl_command_argv)
        cmd.extend(args)
        try:
            completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RuntimeControlError(str(exc)) from exc
        except subprocess.CalledProcessError as exc:
            output = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise RuntimeControlError(output) from exc
        return completed.stdout

    def _parse_show_output(self, output: str) -> dict[str, str]:
        properties: dict[str, str] = {}
        for line in output.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            properties[key] = value
        return properties

    def _parse_pid(self, value: str) -> int | None:
        try:
            pid = int(value)
        except ValueError:
            return None
        return pid if pid > 0 else None

    def _parse_usec_timestamp(self, value: str) -> datetime | None:
        try:
            usec = int(value)
        except ValueError:
            return None
        if usec <= 0:
            return None
        return datetime.fromtimestamp(usec / 1_000_000, tz=timezone.utc)

    def _map_active_state(self, active_state: str) -> str:
        return {
            "active": RUNTIME_STATE_RUNNING,
            "activating": RUNTIME_STATE_STARTING,
            "deactivating": RUNTIME_STATE_STOPPING,
            "failed": RUNTIME_STATE_ERROR,
            "inactive": RUNTIME_STATE_STOPPED,
        }.get(active_state, RUNTIME_STATE_ERROR)


class NullController:
    controller_kind = RUNTIME_CONTROLLER_NONE

    def start(self, unit_name: str) -> SystemdUnitStatus:
        raise RuntimeControlError("systemd is not available")

    def stop(self, unit_name: str) -> SystemdUnitStatus:
        return self.status(unit_name)

    def restart(self, unit_name: str) -> SystemdUnitStatus:
        raise RuntimeControlError("systemd is not available")

    def reload(self, unit_name: str) -> SystemdUnitStatus:
        raise RuntimeControlError("systemd is not available")

    def status(self, unit_name: str) -> SystemdUnitStatus:
        return SystemdUnitStatus(unit_name=unit_name, state=RUNTIME_STATE_ERROR)


def build_systemd_controller(settings: Settings) -> SystemdController | NullController:
    try:
        return SystemdController(settings)
    except RuntimeControlError:
        return NullController()
