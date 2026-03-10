#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  printf '[deploy] error: run this script with bash, for example: sudo bash deploy/install-native.sh\n' >&2
  exit 1
fi

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

APP_USER="${APP_USER:-claw-manager}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/claw-workspace-manager}"
APP_ROOT="${APP_ROOT:-$INSTALL_ROOT/app}"
VENV_DIR="${VENV_DIR:-$INSTALL_ROOT/venv}"
DATA_ROOT="${DATA_ROOT:-/srv/claw}"
ENV_FILE="${ENV_FILE:-/etc/claw-workspace-manager.env}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
SUDOERS_FILE="${SUDOERS_FILE:-/etc/sudoers.d/claw-workspace-manager}"
MANAGER_SERVICE="${MANAGER_SERVICE:-claw-manager.service}"
OPENCLAW_SHARED_UNIT="${OPENCLAW_SHARED_UNIT:-claw-openclaw.service}"
NANOBOT_UNIT_TEMPLATE="${NANOBOT_UNIT_TEMPLATE:-claw-nanobot@{workspace_id}.service}"
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

SQLITE_PATH_DEFAULT="$DATA_ROOT/sqlite/app.db"
WORKSPACE_ROOT_DEFAULT="$DATA_ROOT/workspaces"
RUNTIME_STATE_ROOT_DEFAULT="$DATA_ROOT/runtime"
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
  if [[ "$NANOBOT_UNIT_TEMPLATE" == *"{workspace_id.service}"* ]]; then
    warn "normalizing legacy NANOBOT_UNIT_TEMPLATE placeholder {workspace_id.service} to {workspace_id}.service"
    NANOBOT_UNIT_TEMPLATE="${NANOBOT_UNIT_TEMPLATE//\{workspace_id.service\}/\{workspace_id\}.service}"
  fi

  if [[ "$NANOBOT_UNIT_TEMPLATE" != *"{workspace_id}"* ]]; then
    die "NANOBOT_UNIT_TEMPLATE must contain the literal placeholder {workspace_id}"
  fi

  local remainder="${NANOBOT_UNIT_TEMPLATE/\{workspace_id\}/}"
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

load_existing_env() {
  if [ ! -f "$ENV_FILE" ]; then
    return
  fi
  if [ -z "${SESSION_SECRET:-}" ]; then
    SESSION_SECRET="$(awk -F= '$1 == "SESSION_SECRET" {print substr($0, index($0, "=") + 1); exit}' "$ENV_FILE")"
  fi
  if [ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    BOOTSTRAP_ADMIN_PASSWORD="$(
      awk -F= '$1 == "BOOTSTRAP_ADMIN_PASSWORD" {print substr($0, index($0, "=") + 1); exit}' "$ENV_FILE"
    )"
  fi
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

ensure_directories() {
  install -d "$INSTALL_ROOT"
  install -d "$APP_ROOT"
  install -d "$VENV_DIR"
  install -d "$DATA_ROOT/sqlite"
  install -d "$WORKSPACE_ROOT_DEFAULT"
  install -d "$RUNTIME_STATE_ROOT_DEFAULT/openclaw"
  install -d "$RUNTIME_STATE_ROOT_DEFAULT/nanobot"
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
SESSION_SECRET=$SESSION_SECRET
SQLITE_PATH=$SQLITE_PATH_DEFAULT
WORKSPACE_ROOT=$WORKSPACE_ROOT_DEFAULT
HOST_WORKSPACE_ROOT=$WORKSPACE_ROOT_DEFAULT
RUNTIME_STATE_ROOT=$RUNTIME_STATE_ROOT_DEFAULT
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
  local aggregate_file="$RUNTIME_STATE_ROOT_DEFAULT/openclaw/openclaw.json"
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
User=$APP_USER
Group=$APP_GROUP
Environment=OPENCLAW_BIN=$OPENCLAW_BIN
Environment=CLAW_RUNTIME_ROOT=$RUNTIME_STATE_ROOT_DEFAULT
ExecStart=/bin/sh -lc '"\$OPENCLAW_BIN" gateway --config "\$CLAW_RUNTIME_ROOT/openclaw/openclaw.json"'
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=3
WorkingDirectory=$RUNTIME_STATE_ROOT_DEFAULT/openclaw

[Install]
WantedBy=multi-user.target
EOF
}

write_nanobot_unit() {
  local unit_name="${NANOBOT_UNIT_TEMPLATE/\{workspace_id\}/%i}"
  local unit_file="$SYSTEMD_DIR/$unit_name"
  log "installing Nanobot workspace runtime unit $unit_file"
  cat >"$unit_file" <<EOF
[Unit]
Description=Claw Nanobot Runtime for workspace %i
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
Environment=NANOBOT_BIN=$NANOBOT_BIN
EnvironmentFile=$RUNTIME_STATE_ROOT_DEFAULT/nanobot/%i/runtime.env
ExecStart=/bin/sh -lc '"\$NANOBOT_BIN" gateway --config "\$NANOBOT_CONFIG_PATH" --port "\$NANOBOT_PORT"'
Restart=on-failure
RestartSec=3
WorkingDirectory=$RUNTIME_STATE_ROOT_DEFAULT/nanobot/%i

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
  chown -R "$APP_USER:$APP_GROUP" "$INSTALL_ROOT" "$DATA_ROOT"
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
  printf 'Admin username: %s\n' "$BOOTSTRAP_ADMIN_USERNAME"
  if [ "$GENERATED_ADMIN_PASSWORD" -eq 1 ]; then
    printf 'Generated admin password: %s\n' "$BOOTSTRAP_ADMIN_PASSWORD"
  fi
  if [ ! -x "$OPENCLAW_BIN" ]; then
    warn "OpenClaw binary not found at $OPENCLAW_BIN; shared runtime unit will not start until you install it"
  fi
  if [ ! -x "$NANOBOT_BIN" ]; then
    warn "Nanobot binary not found at $NANOBOT_BIN; workspace runtimes will not start until you install it"
  fi
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

main "$@"
