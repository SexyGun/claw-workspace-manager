#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  printf '[deploy] error: run this script with bash, for example: sudo bash deploy/install-native.sh\n' >&2
  exit 1
fi

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

APP_USER_WAS_SET="${APP_USER+x}"
APP_GROUP_WAS_SET="${APP_GROUP+x}"
RUNTIME_USER_WAS_SET="${RUNTIME_USER+x}"
RUNTIME_GROUP_WAS_SET="${RUNTIME_GROUP+x}"
RUNTIME_HOME_WAS_SET="${RUNTIME_HOME+x}"
SQLITE_PATH_WAS_SET="${SQLITE_PATH+x}"
WORKSPACE_ROOT_WAS_SET="${WORKSPACE_ROOT+x}"
HOST_WORKSPACE_ROOT_WAS_SET="${HOST_WORKSPACE_ROOT+x}"
RUNTIME_STATE_ROOT_WAS_SET="${RUNTIME_STATE_ROOT+x}"
OPENCLAW_BIN_WAS_SET="${OPENCLAW_BIN+x}"
NANOBOT_BIN_WAS_SET="${NANOBOT_BIN+x}"
SESSION_SECRET_WAS_SET="${SESSION_SECRET+x}"
BOOTSTRAP_ADMIN_PASSWORD_WAS_SET="${BOOTSTRAP_ADMIN_PASSWORD+x}"

APP_USER="${APP_USER:-claw-manager}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
RUNTIME_USER="${RUNTIME_USER:-}"
RUNTIME_GROUP="${RUNTIME_GROUP:-}"
RUNTIME_HOME="${RUNTIME_HOME:-}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/claw-workspace-manager}"
APP_ROOT="${APP_ROOT:-$INSTALL_ROOT/app}"
VENV_DIR="${VENV_DIR:-$INSTALL_ROOT/venv}"
DATA_ROOT="${DATA_ROOT:-/srv/claw}"
APP_HOME_OVERRIDE="${APP_HOME_OVERRIDE:-}"
LEGACY_WORKSPACE_ROOT="${LEGACY_WORKSPACE_ROOT:-/srv/claw/workspaces}"
SQLITE_PATH="${SQLITE_PATH:-}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-}"
HOST_WORKSPACE_ROOT="${HOST_WORKSPACE_ROOT:-}"
RUNTIME_STATE_ROOT="${RUNTIME_STATE_ROOT:-}"
DEFAULT_NANOBOT_UNIT_TEMPLATE='claw-nanobot@{workspace_id}.service'
ENV_FILE="${ENV_FILE:-/etc/claw-workspace-manager.env}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
SUDOERS_FILE="${SUDOERS_FILE:-/etc/sudoers.d/claw-workspace-manager}"
MANAGER_SERVICE="${MANAGER_SERVICE:-claw-manager.service}"
OPENCLAW_SHARED_UNIT="${OPENCLAW_SHARED_UNIT:-claw-openclaw.service}"
NANOBOT_UNIT_TEMPLATE="${NANOBOT_UNIT_TEMPLATE:-$DEFAULT_NANOBOT_UNIT_TEMPLATE}"
MANAGER_HOST="${MANAGER_HOST:-0.0.0.0}"
MANAGER_PORT="${MANAGER_PORT:-8000}"
RUNTIME_HOST="${RUNTIME_HOST:-127.0.0.1}"
NANOBOT_PORT_BASE="${NANOBOT_PORT_BASE:-18080}"
OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-7331}"
BOOTSTRAP_ADMIN_USERNAME="${BOOTSTRAP_ADMIN_USERNAME:-admin}"
APP_ENV="${APP_ENV:-production}"

SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-$(command -v systemctl || true)}"
SUDO_BIN="${SUDO_BIN:-$(command -v sudo || true)}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
NPM_BIN="${NPM_BIN:-$(command -v npm || true)}"
OPENCLAW_BIN="${OPENCLAW_BIN:-/usr/local/bin/openclaw}"
NANOBOT_BIN="${NANOBOT_BIN:-/usr/local/bin/nanobot}"
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-}"
PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-120}"
PIP_RETRIES="${PIP_RETRIES:-5}"

APP_HOME=""
SQLITE_PATH_DEFAULT=""
WORKSPACE_ROOT_DEFAULT=""
HOST_WORKSPACE_ROOT_DEFAULT=""
RUNTIME_STATE_ROOT_DEFAULT=""
WORKSPACE_TEMPLATE_ROOT_DEFAULT="$APP_ROOT/deploy/templates/base-workspace"
OPENCLAW_WORKSPACE_TEMPLATE_ROOT_DEFAULT="$APP_ROOT/deploy/templates/openclaw-workspace"

GENERATED_ADMIN_PASSWORD=0

log() {
  printf '[deploy] %s\n' "$*"
}

warn() {
  printf '[deploy] warning: %s\n' "$*" >&2
}

die() {
  printf '[deploy] error: %s\n' "$*" >&2
  exit 1
}

is_interactive_terminal() {
  [ -t 0 ] && [ -t 1 ]
}

prompt_with_default() {
  local prompt="$1"
  local default_value="$2"
  local response=""
  if [ -n "$default_value" ]; then
    printf '%s [%s]: ' "$prompt" "$default_value" >&2
  else
    printf '%s: ' "$prompt" >&2
  fi
  read -r response
  if [ -z "$response" ]; then
    printf '%s\n' "$default_value"
    return
  fi
  printf '%s\n' "$response"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    die "run this script as root, for example: sudo bash deploy/install-native.sh"
  fi
}

require_cmd() {
  local name="$1"
  local value="$2"
  if [ -z "$value" ]; then
    die "missing required command: $name"
  fi
}

python_major_minor() {
  "$PYTHON_BIN" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
}

check_python_venv_support() {
  if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import ensurepip  # noqa: F401
import venv  # noqa: F401
PY
  then
    return
  fi

  local version
  version="$(python_major_minor)"
  if command -v apt-get >/dev/null 2>&1; then
    die "python3 venv support is missing. Install it first with: sudo apt install -y python${version}-venv or sudo apt install -y python3-venv"
  fi
  if command -v dnf >/dev/null 2>&1; then
    die "python3 venv support is missing. Install the matching venv package for Python ${version} with dnf, then rerun this script"
  fi
  if command -v yum >/dev/null 2>&1; then
    die "python3 venv support is missing. Install the matching venv package for Python ${version} with yum, then rerun this script"
  fi
  die "python3 venv support is missing. Install the ensurepip/venv package for Python ${version}, then rerun this script"
}

detect_nologin() {
  if [ -x /usr/sbin/nologin ]; then
    printf '%s\n' /usr/sbin/nologin
    return
  fi
  if [ -x /sbin/nologin ]; then
    printf '%s\n' /sbin/nologin
    return
  fi
  printf '%s\n' /usr/bin/false
}

normalize_nanobot_unit_template() {
  local legacy_placeholder="{workspace_id.service}"
  local placeholder="{workspace_id}"
  local prefix=""
  local remainder=""
  local suffix=""

  if [[ "$NANOBOT_UNIT_TEMPLATE" == *"$legacy_placeholder"* ]]; then
    warn "normalizing legacy NANOBOT_UNIT_TEMPLATE placeholder {workspace_id.service} to {workspace_id}.service"
    NANOBOT_UNIT_TEMPLATE="${NANOBOT_UNIT_TEMPLATE//$legacy_placeholder/$placeholder.service}"
  fi

  if [[ "$NANOBOT_UNIT_TEMPLATE" != *"$placeholder"* ]]; then
    die "NANOBOT_UNIT_TEMPLATE must contain the literal placeholder {workspace_id}"
  fi

  prefix="${NANOBOT_UNIT_TEMPLATE%%"$placeholder"*}"
  suffix="${NANOBOT_UNIT_TEMPLATE#*"$placeholder"}"
  remainder="${prefix}${suffix}"
  if [[ "$remainder" == *"{"* ]] || [[ "$remainder" == *"}"* ]]; then
    die "NANOBOT_UNIT_TEMPLATE contains unsupported braces; use a value like claw-nanobot@{workspace_id}.service"
  fi
}

generate_secret() {
  "$PYTHON_BIN" - <<'PY'
from secrets import token_urlsafe
print(token_urlsafe(32))
PY
}

read_env_value() {
  local key="$1"
  awk -F= -v target="$key" '$1 == target {print substr($0, index($0, "=") + 1); exit}' "$ENV_FILE"
}

load_existing_env() {
  if [ ! -f "$ENV_FILE" ]; then
    return
  fi
  if [ -z "$APP_USER_WAS_SET" ]; then
    APP_USER="$(read_env_value APP_USER)"
  fi
  if [ -z "$APP_GROUP_WAS_SET" ]; then
    APP_GROUP="$(read_env_value APP_GROUP)"
  fi
  if [ -z "$RUNTIME_USER_WAS_SET" ]; then
    RUNTIME_USER="$(read_env_value RUNTIME_USER)"
  fi
  if [ -z "$RUNTIME_GROUP_WAS_SET" ]; then
    RUNTIME_GROUP="$(read_env_value RUNTIME_GROUP)"
  fi
  if [ -z "$RUNTIME_HOME_WAS_SET" ]; then
    RUNTIME_HOME="$(read_env_value RUNTIME_HOME)"
  fi
  if [ -z "$SQLITE_PATH_WAS_SET" ]; then
    SQLITE_PATH="$(read_env_value SQLITE_PATH)"
  fi
  if [ -z "$WORKSPACE_ROOT_WAS_SET" ]; then
    WORKSPACE_ROOT="$(read_env_value WORKSPACE_ROOT)"
  fi
  if [ -z "$HOST_WORKSPACE_ROOT_WAS_SET" ]; then
    HOST_WORKSPACE_ROOT="$(read_env_value HOST_WORKSPACE_ROOT)"
  fi
  if [ -z "$RUNTIME_STATE_ROOT_WAS_SET" ]; then
    RUNTIME_STATE_ROOT="$(read_env_value RUNTIME_STATE_ROOT)"
  fi
  if [ -z "$OPENCLAW_BIN_WAS_SET" ]; then
    OPENCLAW_BIN="$(read_env_value OPENCLAW_BIN)"
  fi
  if [ -z "$NANOBOT_BIN_WAS_SET" ]; then
    NANOBOT_BIN="$(read_env_value NANOBOT_BIN)"
  fi
  if [ -z "$SESSION_SECRET_WAS_SET" ]; then
    SESSION_SECRET="$(read_env_value SESSION_SECRET)"
  fi
  if [ -z "$BOOTSTRAP_ADMIN_PASSWORD_WAS_SET" ]; then
    BOOTSTRAP_ADMIN_PASSWORD="$(read_env_value BOOTSTRAP_ADMIN_PASSWORD)"
  fi

  APP_USER="${APP_USER:-claw-manager}"
  APP_GROUP="${APP_GROUP:-$APP_USER}"
  OPENCLAW_BIN="${OPENCLAW_BIN:-/usr/local/bin/openclaw}"
  NANOBOT_BIN="${NANOBOT_BIN:-/usr/local/bin/nanobot}"
}

ensure_group() {
  if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
    log "creating group $APP_GROUP"
    groupadd --system "$APP_GROUP"
  fi
}

ensure_user() {
  local nologin_bin
  nologin_bin="$(detect_nologin)"
  if ! id "$APP_USER" >/dev/null 2>&1; then
    log "creating user $APP_USER"
    useradd \
      --system \
      --gid "$APP_GROUP" \
      --home-dir "$INSTALL_ROOT/home" \
      --create-home \
      --shell "$nologin_bin" \
      "$APP_USER"
  fi
}

resolve_user_home() {
  local username="$1"
  getent passwd "$username" | awk -F: '{print $6}'
}

resolve_app_home() {
  if [ -n "$APP_HOME_OVERRIDE" ]; then
    printf '%s\n' "$APP_HOME_OVERRIDE"
    return
  fi
  resolve_user_home "$APP_USER"
}

detect_binary_for_user() {
  local binary_name="$1"
  local username="$2"
  local user_home="$3"
  local candidate=""
  local -a home_candidates

  home_candidates=(
    "$user_home/.npm-global/bin/$binary_name"
    "$user_home/.local/bin/$binary_name"
  )

  for candidate in "${home_candidates[@]}"; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  if candidate="$("$SUDO_BIN" -u "$username" env HOME="$user_home" /bin/sh -lc "command -v $binary_name" 2>/dev/null)"; then
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  fi
}

resolve_binary_path() {
  local label="$1"
  local binary_name="$2"
  local configured_path="$3"
  local username="$4"
  local user_home="$5"
  local detected_path=""

  if [ -n "$configured_path" ] && [ -x "$configured_path" ]; then
    printf '%s\n' "$configured_path"
    return
  fi

  detected_path="$(detect_binary_for_user "$binary_name" "$username" "$user_home")"
  if [ -n "$detected_path" ]; then
    if [ -n "$configured_path" ] && [ "$configured_path" != "$detected_path" ]; then
      warn "$label binary path $configured_path is unusable; switching to detected path $detected_path"
    else
      log "detected $label binary at $detected_path"
    fi
    printf '%s\n' "$detected_path"
    return
  fi

  printf '%s\n' "$configured_path"
}

binary_issue_for_user() {
  local bin_path="$1"
  local service_user="$2"

  if [ -z "$bin_path" ]; then
    printf '%s\n' "binary path is empty"
    return
  fi
  if [ ! -e "$bin_path" ]; then
    printf '%s\n' "binary not found at $bin_path"
    return
  fi
  if [ ! -x "$bin_path" ]; then
    printf '%s\n' "binary exists at $bin_path but is not executable"
    return
  fi
  if ! "$SUDO_BIN" -u "$service_user" env CLAW_BIN_PATH="$bin_path" /bin/sh -lc 'test -x "$CLAW_BIN_PATH"' 2>/dev/null; then
    printf '%s\n' "binary at $bin_path is not executable by runtime user $service_user"
    return
  fi
  printf '%s\n' ""
}

ensure_binary_access() {
  local label="$1"
  local binary_name="$2"
  local var_name="$3"
  local service_user="$4"
  local service_home="$5"
  local current_path="${!var_name}"
  local issue=""
  local detected_path=""
  local next_path=""

  while true; do
    current_path="${!var_name}"
    issue="$(binary_issue_for_user "$current_path" "$service_user")"
    if [ -z "$issue" ]; then
      return
    fi
    if ! is_interactive_terminal; then
      return
    fi

    warn "$label $issue"
    detected_path="$(detect_binary_for_user "$binary_name" "$service_user" "$service_home")"
    next_path="$current_path"
    if [ -n "$detected_path" ] && [ "$detected_path" != "$current_path" ]; then
      next_path="$detected_path"
    fi
    next_path="$(prompt_with_default "Enter $label binary path for service user $service_user" "$next_path")"
    if [ -n "$next_path" ]; then
      printf -v "$var_name" '%s' "$next_path"
    fi
  done
}

ensure_single_user_runtime() {
  local resolved_home=""

  if [ -n "$RUNTIME_USER" ] && [ "$RUNTIME_USER" != "$APP_USER" ]; then
    if [ -z "$RUNTIME_USER_WAS_SET" ]; then
      warn "ignoring legacy RUNTIME_USER=$RUNTIME_USER from existing env; runtime now follows APP_USER=$APP_USER"
      RUNTIME_USER=""
    else
      die "RUNTIME_USER must match APP_USER; separate runtime users are no longer supported"
    fi
  fi
  if [ -n "$RUNTIME_GROUP" ] && [ "$RUNTIME_GROUP" != "$APP_GROUP" ]; then
    if [ -z "$RUNTIME_GROUP_WAS_SET" ]; then
      warn "ignoring legacy RUNTIME_GROUP=$RUNTIME_GROUP from existing env; runtime now follows APP_GROUP=$APP_GROUP"
      RUNTIME_GROUP=""
    else
      die "RUNTIME_GROUP must match APP_GROUP; separate runtime groups are no longer supported"
    fi
  fi

  resolved_home="$(resolve_app_home)"
  if [ -z "$resolved_home" ]; then
    die "unable to determine home directory for APP_USER $APP_USER"
  fi
  if [ ! -d "$resolved_home" ]; then
    die "APP_USER home directory does not exist: $resolved_home"
  fi
  if [ -n "$RUNTIME_HOME" ] && [ "$RUNTIME_HOME" != "$resolved_home" ]; then
    if [ -z "$RUNTIME_HOME_WAS_SET" ]; then
      warn "ignoring legacy RUNTIME_HOME=$RUNTIME_HOME from existing env; runtime home now follows APP_USER home $resolved_home"
      RUNTIME_HOME=""
    else
      die "RUNTIME_HOME must match APP_USER home $resolved_home; separate runtime homes are no longer supported"
    fi
  fi

  APP_HOME="$resolved_home"
  RUNTIME_USER="$APP_USER"
  RUNTIME_GROUP="$APP_GROUP"
  RUNTIME_HOME="$APP_HOME"
}

ensure_runtime_binaries() {
  OPENCLAW_BIN="$(resolve_binary_path "OpenClaw" "openclaw" "$OPENCLAW_BIN" "$APP_USER" "$APP_HOME")"
  NANOBOT_BIN="$(resolve_binary_path "Nanobot" "nanobot" "$NANOBOT_BIN" "$APP_USER" "$APP_HOME")"
  ensure_binary_access "OpenClaw" "openclaw" OPENCLAW_BIN "$APP_USER" "$APP_HOME"
  ensure_binary_access "Nanobot" "nanobot" NANOBOT_BIN "$APP_USER" "$APP_HOME"
}

warn_if_binary_unusable_by_service_user() {
  local label="$1"
  local bin_path="$2"
  local service_user="$3"
  if [ ! -e "$bin_path" ]; then
    warn "$label binary not found at $bin_path; related runtimes will not start until you install it"
    return
  fi
  if [ ! -x "$bin_path" ]; then
    warn "$label binary exists at $bin_path but is not executable"
    return
  fi
  if ! "$SUDO_BIN" -u "$service_user" env CLAW_BIN_PATH="$bin_path" /bin/sh -lc 'test -x "$CLAW_BIN_PATH"'; then
    warn "$label binary at $bin_path is not executable by service user $service_user; avoid per-user install paths under /home and use a shared location like /usr/local/bin"
  fi
}

initialize_paths() {
  SQLITE_PATH_DEFAULT="$DATA_ROOT/sqlite/app.db"
  RUNTIME_STATE_ROOT_DEFAULT="$DATA_ROOT/runtime"
  WORKSPACE_ROOT_DEFAULT="$APP_HOME/claw"
  HOST_WORKSPACE_ROOT_DEFAULT="$WORKSPACE_ROOT_DEFAULT"

  SQLITE_PATH="${SQLITE_PATH:-$SQLITE_PATH_DEFAULT}"
  RUNTIME_STATE_ROOT="${RUNTIME_STATE_ROOT:-$RUNTIME_STATE_ROOT_DEFAULT}"

  if [ -z "$WORKSPACE_ROOT" ] || [ "$WORKSPACE_ROOT" = "$LEGACY_WORKSPACE_ROOT" ]; then
    WORKSPACE_ROOT="$WORKSPACE_ROOT_DEFAULT"
  fi
  if [ -z "$HOST_WORKSPACE_ROOT" ]; then
    HOST_WORKSPACE_ROOT="$WORKSPACE_ROOT"
  elif [ "$HOST_WORKSPACE_ROOT" = "$LEGACY_WORKSPACE_ROOT" ]; then
    HOST_WORKSPACE_ROOT="$WORKSPACE_ROOT_DEFAULT"
  fi
}

path_has_entries() {
  local path="$1"
  find "$path" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .
}

migrate_legacy_workspace_root_if_needed() {
  if [ "$WORKSPACE_ROOT" != "$WORKSPACE_ROOT_DEFAULT" ] || [ "$HOST_WORKSPACE_ROOT" != "$WORKSPACE_ROOT_DEFAULT" ]; then
    return
  fi
  if [ -z "$LEGACY_WORKSPACE_ROOT" ] || [ "$LEGACY_WORKSPACE_ROOT" = "$WORKSPACE_ROOT" ] || [ ! -d "$LEGACY_WORKSPACE_ROOT" ]; then
    return
  fi
  if [ -e "$WORKSPACE_ROOT" ]; then
    if [ ! -d "$WORKSPACE_ROOT" ]; then
      die "workspace root target exists and is not a directory: $WORKSPACE_ROOT"
    fi
    if path_has_entries "$WORKSPACE_ROOT"; then
      die "both legacy workspace root $LEGACY_WORKSPACE_ROOT and new workspace root $WORKSPACE_ROOT exist; move data manually"
    fi
    rmdir "$WORKSPACE_ROOT"
  fi

  log "migrating legacy workspace root from $LEGACY_WORKSPACE_ROOT to $WORKSPACE_ROOT"
  install -d "$(dirname "$WORKSPACE_ROOT")"
  mv "$LEGACY_WORKSPACE_ROOT" "$WORKSPACE_ROOT"
}

ensure_directories() {
  install -d "$INSTALL_ROOT"
  install -d "$APP_ROOT"
  install -d "$VENV_DIR"
  install -d "$(dirname "$ENV_FILE")"
  install -d "$SYSTEMD_DIR"
  install -d "$(dirname "$SUDOERS_FILE")"
  install -d "$(dirname "$SQLITE_PATH")"
  install -d "$WORKSPACE_ROOT"
  install -d "$HOST_WORKSPACE_ROOT"
  install -d "$RUNTIME_STATE_ROOT/openclaw"
  install -d "$RUNTIME_STATE_ROOT/nanobot"
}

guard_install_path() {
  case "$APP_ROOT" in
    "$REPO_ROOT"|"$REPO_ROOT"/*)
      die "APP_ROOT must be outside the source repository"
      ;;
  esac
}

sync_source_tree() {
  log "syncing repository into $APP_ROOT"
  find "$APP_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  cp -a "$REPO_ROOT/." "$APP_ROOT/"
  rm -rf \
    "$APP_ROOT/.git" \
    "$APP_ROOT/backend/.data" \
    "$APP_ROOT/backend/.pytest_cache" \
    "$APP_ROOT/frontend/node_modules" \
    "$APP_ROOT/frontend/dist"
  find "$APP_ROOT" -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +
}

install_backend() {
  log "installing backend dependencies"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  local -a pip_args
  pip_args=(
    --default-timeout "$PIP_DEFAULT_TIMEOUT"
    --retries "$PIP_RETRIES"
  )
  if [ -n "$PIP_INDEX_URL" ]; then
    pip_args+=(--index-url "$PIP_INDEX_URL")
  fi
  if [ -n "$PIP_EXTRA_INDEX_URL" ]; then
    pip_args+=(--extra-index-url "$PIP_EXTRA_INDEX_URL")
  fi
  if ! "$VENV_DIR/bin/pip" install "${pip_args[@]}" "$APP_ROOT/backend"; then
    die "pip install failed. Check network access to your package index, or rerun with PIP_INDEX_URL / PIP_DEFAULT_TIMEOUT / PIP_RETRIES overrides"
  fi
}

build_frontend() {
  log "building frontend"
  (
    cd "$APP_ROOT/frontend"
    if [ -f package-lock.json ]; then
      "$NPM_BIN" ci
    else
      "$NPM_BIN" install
    fi
    "$NPM_BIN" run build
  )
  rm -rf "$APP_ROOT/backend/app/static"
  install -d "$APP_ROOT/backend/app/static"
  cp -a "$APP_ROOT/frontend/dist/." "$APP_ROOT/backend/app/static/"
}

write_env_file() {
  log "writing environment file $ENV_FILE"
  cat >"$ENV_FILE" <<EOF
APP_ENV=$APP_ENV
APP_USER=$APP_USER
APP_GROUP=$APP_GROUP
RUNTIME_USER=$RUNTIME_USER
RUNTIME_GROUP=$RUNTIME_GROUP
RUNTIME_HOME=$RUNTIME_HOME
OPENCLAW_BIN=$OPENCLAW_BIN
NANOBOT_BIN=$NANOBOT_BIN
SESSION_SECRET=$SESSION_SECRET
SQLITE_PATH=$SQLITE_PATH
WORKSPACE_ROOT=$WORKSPACE_ROOT
HOST_WORKSPACE_ROOT=$HOST_WORKSPACE_ROOT
RUNTIME_STATE_ROOT=$RUNTIME_STATE_ROOT
WORKSPACE_TEMPLATE_ROOT=$WORKSPACE_TEMPLATE_ROOT_DEFAULT
OPENCLAW_WORKSPACE_TEMPLATE_ROOT=$OPENCLAW_WORKSPACE_TEMPLATE_ROOT_DEFAULT
SYSTEMCTL_COMMAND=$SYSTEMCTL_BIN
SYSTEMCTL_USE_SUDO=true
SUDO_COMMAND=$SUDO_BIN
NANOBOT_UNIT_TEMPLATE=$NANOBOT_UNIT_TEMPLATE
OPENCLAW_SHARED_UNIT=$OPENCLAW_SHARED_UNIT
RUNTIME_HOST=$RUNTIME_HOST
NANOBOT_PORT_BASE=$NANOBOT_PORT_BASE
OPENCLAW_GATEWAY_PORT=$OPENCLAW_GATEWAY_PORT
BOOTSTRAP_ADMIN_USERNAME=$BOOTSTRAP_ADMIN_USERNAME
BOOTSTRAP_ADMIN_PASSWORD=$BOOTSTRAP_ADMIN_PASSWORD
MANAGER_HOST=$MANAGER_HOST
MANAGER_PORT=$MANAGER_PORT
EOF
  chmod 0600 "$ENV_FILE"
}

write_openclaw_bootstrap_config() {
  local aggregate_file="$RUNTIME_STATE_ROOT/openclaw/openclaw.json"
  if [ -f "$aggregate_file" ]; then
    return
  fi
  log "creating initial OpenClaw aggregate config"
  cat >"$aggregate_file" <<EOF
{
  "gateway": {
    "port": $OPENCLAW_GATEWAY_PORT
  },
  "channels": {
    "feishu": {
      "accounts": []
    }
  },
  "agents": {
    "list": []
  },
  "bindings": []
}
EOF
}

write_manager_unit() {
  local unit_file="$SYSTEMD_DIR/$MANAGER_SERVICE"
  log "installing manager service $unit_file"
  cat >"$unit_file" <<EOF
[Unit]
Description=Claw Workspace Manager
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
EnvironmentFile=$ENV_FILE
WorkingDirectory=$APP_ROOT/backend
ExecStartPre=$VENV_DIR/bin/alembic upgrade head
ExecStart=$VENV_DIR/bin/uvicorn app.main:app --host $MANAGER_HOST --port $MANAGER_PORT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
}

write_openclaw_unit() {
  local unit_file="$SYSTEMD_DIR/$OPENCLAW_SHARED_UNIT"
  log "installing OpenClaw shared runtime unit $unit_file"
  cat >"$unit_file" <<EOF
[Unit]
Description=Claw OpenClaw Shared Runtime
After=network.target

[Service]
Type=simple
User=$RUNTIME_USER
Group=$RUNTIME_GROUP
EnvironmentFile=$ENV_FILE
Environment=HOME=$RUNTIME_HOME
Environment=CLAW_RUNTIME_ROOT=$RUNTIME_STATE_ROOT
Environment=OPENCLAW_CONFIG_PATH=$RUNTIME_STATE_ROOT/openclaw/openclaw.json
ExecStart=/bin/sh -lc '"\$OPENCLAW_BIN" gateway'
ExecReload=/bin/kill -HUP \$MAINPID
UMask=0002
Restart=on-failure
RestartSec=3
WorkingDirectory=$RUNTIME_STATE_ROOT/openclaw

[Install]
WantedBy=multi-user.target
EOF
}

write_nanobot_unit() {
  local template_unit_name="${NANOBOT_UNIT_TEMPLATE/\{workspace_id\}/}"
  local unit_file="$SYSTEMD_DIR/$template_unit_name"
  log "installing Nanobot workspace runtime unit $unit_file"
  cat >"$unit_file" <<EOF
[Unit]
Description=Claw Nanobot Runtime for workspace %i
After=network.target

[Service]
Type=simple
User=$RUNTIME_USER
Group=$RUNTIME_GROUP
EnvironmentFile=$ENV_FILE
Environment=HOME=$RUNTIME_HOME
EnvironmentFile=$RUNTIME_STATE_ROOT/nanobot/%i/runtime.env
ExecStart=/bin/sh -lc '"\$NANOBOT_BIN" gateway --config "\$NANOBOT_CONFIG_PATH" --port "\$NANOBOT_PORT"'
KillMode=control-group
KillSignal=SIGTERM
TimeoutStopSec=15
UMask=0002
Restart=on-failure
RestartSec=3
WorkingDirectory=$RUNTIME_STATE_ROOT/nanobot/%i

[Install]
WantedBy=multi-user.target
EOF
}

write_sudoers_file() {
  local nanobot_unit_glob="${NANOBOT_UNIT_TEMPLATE/\{workspace_id\}/*}"
  log "installing sudoers policy $SUDOERS_FILE"
  cat >"$SUDOERS_FILE" <<EOF
# Managed by deploy/install-native.sh
Cmnd_Alias CLAW_OPENCLAW = \\
    $SYSTEMCTL_BIN start $OPENCLAW_SHARED_UNIT, \\
    $SYSTEMCTL_BIN stop $OPENCLAW_SHARED_UNIT, \\
    $SYSTEMCTL_BIN restart $OPENCLAW_SHARED_UNIT, \\
    $SYSTEMCTL_BIN reload $OPENCLAW_SHARED_UNIT, \\
    $SYSTEMCTL_BIN show $OPENCLAW_SHARED_UNIT *

Cmnd_Alias CLAW_NANOBOT = \\
    $SYSTEMCTL_BIN start $nanobot_unit_glob, \\
    $SYSTEMCTL_BIN stop $nanobot_unit_glob, \\
    $SYSTEMCTL_BIN restart $nanobot_unit_glob, \\
    $SYSTEMCTL_BIN show $nanobot_unit_glob *

$APP_USER ALL=(root) NOPASSWD: CLAW_OPENCLAW, CLAW_NANOBOT
EOF
  chmod 0440 "$SUDOERS_FILE"
}

set_permissions() {
  local sqlite_dir
  sqlite_dir="$(dirname "$SQLITE_PATH")"
  chown -R "$APP_USER:$APP_GROUP" "$INSTALL_ROOT"
  chown -R "$APP_USER:$APP_GROUP" "$WORKSPACE_ROOT"
  if [ "$HOST_WORKSPACE_ROOT" != "$WORKSPACE_ROOT" ]; then
    chown -R "$APP_USER:$APP_GROUP" "$HOST_WORKSPACE_ROOT"
  fi
  chown -R "$APP_USER:$APP_GROUP" "$RUNTIME_STATE_ROOT"
  chown -R "$APP_USER:$APP_GROUP" "$sqlite_dir"
}

start_manager_service() {
  log "reloading systemd and starting $MANAGER_SERVICE"
  "$SYSTEMCTL_BIN" daemon-reload
  "$SYSTEMCTL_BIN" enable "$MANAGER_SERVICE"
  "$SYSTEMCTL_BIN" restart "$MANAGER_SERVICE"
}

print_summary() {
  printf '\n'
  printf 'Claw Workspace Manager is running.\n'
  printf 'Manager URL: http://<server>:%s\n' "$MANAGER_PORT"
  printf 'Service: %s\n' "$MANAGER_SERVICE"
  printf 'Env file: %s\n' "$ENV_FILE"
  printf 'Install root: %s\n' "$INSTALL_ROOT"
  printf 'Data root: %s\n' "$DATA_ROOT"
  printf 'Workspace root: %s\n' "$WORKSPACE_ROOT"
  printf 'Admin username: %s\n' "$BOOTSTRAP_ADMIN_USERNAME"
  printf 'Runtime user: %s\n' "$RUNTIME_USER"
  printf 'Runtime home: %s\n' "$RUNTIME_HOME"
  if [ "$GENERATED_ADMIN_PASSWORD" -eq 1 ]; then
    printf 'Generated admin password: %s\n' "$BOOTSTRAP_ADMIN_PASSWORD"
  fi
  warn_if_binary_unusable_by_service_user "OpenClaw" "$OPENCLAW_BIN" "$RUNTIME_USER"
  warn_if_binary_unusable_by_service_user "Nanobot" "$NANOBOT_BIN" "$RUNTIME_USER"
}

main() {
  require_root
  require_cmd systemctl "$SYSTEMCTL_BIN"
  require_cmd sudo "$SUDO_BIN"
  require_cmd python3 "$PYTHON_BIN"
  require_cmd npm "$NPM_BIN"
  check_python_venv_support
  normalize_nanobot_unit_template
  guard_install_path
  load_existing_env
  SESSION_SECRET="${SESSION_SECRET:-$(generate_secret)}"
  if [ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    BOOTSTRAP_ADMIN_PASSWORD="$(generate_secret)"
    GENERATED_ADMIN_PASSWORD=1
  fi
  ensure_group
  ensure_user
  ensure_single_user_runtime
  initialize_paths
  migrate_legacy_workspace_root_if_needed
  ensure_runtime_binaries
  warn_if_binary_unusable_by_service_user "OpenClaw" "$OPENCLAW_BIN" "$RUNTIME_USER"
  warn_if_binary_unusable_by_service_user "Nanobot" "$NANOBOT_BIN" "$RUNTIME_USER"
  ensure_directories
  sync_source_tree
  install_backend
  build_frontend
  write_env_file
  write_openclaw_bootstrap_config
  write_manager_unit
  write_openclaw_unit
  write_nanobot_unit
  write_sudoers_file
  set_permissions
  start_manager_service
  print_summary
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
