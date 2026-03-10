# Claw 工作区管理器

面向单台 Linux 主机的多用户工作区管理器，当前仅支持原生部署。

## 项目定位

Claw 工作区管理器用于把“用户 / workspace / 运行时实例”这三层关系显式管理起来。它不直接实现 OpenClaw 或 Nanobot 本身的业务逻辑，而是提供一层控制面，用来完成：

- 用户与权限管理
- workspace 生命周期管理
- 配置模板初始化与配置文件渲染
- 原生运行时状态查看与控制
- OpenClaw 多 workspace 聚合路由

目标场景是：在一台受控 Linux 主机上，管理员集中维护 OpenClaw / Nanobot 的运行环境，普通用户只在管理器内创建自己的 workspace、填写渠道配置并查看运行状态。

## 当前状态与能力

- 后端：FastAPI、SQLAlchemy 2、SQLite、Alembic
- 前端：Vue 3、Vite、TypeScript、Naive UI
- 运行模型：
  - OpenClaw 使用单个宿主机共享服务，工作区通过聚合配置路由到不同 agent
  - Nanobot 使用每个 workspace 一个 `systemd` 实例
- 管理器负责用户管理、workspace 目录初始化、配置生成、运行时状态查看与 `systemd` 控制

当前已经支持的核心能力：

- 创建基础 workspace 与 OpenClaw workspace
- 按 workspace 渲染 `.nanobot/config.json` 与运行时 `config.json` / `runtime.env`
- 按 workspace 渲染 `.openclaw/openclaw.json` 与渠道配置
- 聚合所有 OpenClaw workspace 为共享 `openclaw.json`
- 通过 `systemd` 控制 Nanobot workspace 实例
- 查看 OpenClaw 共享服务状态、workspace 路由状态与配置落盘路径
- 在前端直接编辑 Nanobot、OpenClaw agent、OpenClaw 渠道配置，并按“激活 / 停用”管理基础工作区实例

## 运行架构

### OpenClaw

- 宿主机上运行一个共享 OpenClaw 服务
- 每个 OpenClaw workspace 对应一个独立 agent 配置片段
- 管理器将所有 agent、账号和绑定关系聚合到 `RUNTIME_STATE_ROOT/openclaw/openclaw.json`
- 用户在前端保存配置后，管理器重写聚合配置，并在共享服务运行时触发 reload

### Nanobot

- 每个基础 workspace 对应一个独立 Nanobot 运行实例
- 管理器为每个 workspace 分配独立端口，并把实例配置写到 `RUNTIME_STATE_ROOT/nanobot/<workspace_id>/config.json`
- Nanobot 的运行时状态目录来自实例 config 所在目录；管理器同时生成 `runtime.env` 供 `systemd` 模板单元读取
- 前端对基础 workspace 的“激活 / 停用 / 重启”会映射到对应的 `systemd` 模板单元

## 典型使用流程

1. 管理员部署管理器、`systemd` 模板和受限 `sudo` 规则
2. 管理员创建用户或让用户自行登录
3. 用户创建 workspace
4. 管理器按模板初始化目录并渲染默认配置
5. 用户填写渠道凭据、模型参数和运行配置
6. 对于基础 workspace，用户直接控制该 workspace 的 Nanobot 实例
7. 对于 OpenClaw workspace，配置被聚合到共享服务，由共享服务统一对外提供能力

## 当前边界

- 当前仅支持原生运行时，不再提供 Docker/Compose 部署路径
- OpenClaw 路由侧按当前实现以 workspace 绑定单独账号为主
- `systemd` 是默认运行时控制器，未实现 supervisor / launchd 等替代后端
- 项目关注“管理与编排”，不内置 OpenClaw / Nanobot 的安装逻辑

## 仓库结构

- [`backend`](/Users/lichen/zh_workplace/claw-workspace-manager/backend) FastAPI 应用、数据库模型、Alembic 和测试
- [`frontend`](/Users/lichen/zh_workplace/claw-workspace-manager/frontend) Vue 管理控制台
- [`deploy/install-native.sh`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy/install-native.sh) 服务器一键部署并启动脚本
- [`deploy/systemd`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy/systemd) 原生运行时 `systemd` 模板
- [`deploy/sudoers`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy/sudoers) 受限 `sudo` 示例
- [`deploy/templates`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy/templates) 新建 workspace 使用的模板目录

## 本地开发

后端：

```bash
cd backend
python3 -m pip install -e .[dev]
export SESSION_SECRET=dev-secret
export BOOTSTRAP_ADMIN_USERNAME=admin
export BOOTSTRAP_ADMIN_PASSWORD=admin-password
uvicorn app.main:app --reload
```

测试：

```bash
cd backend
pytest
```

前端：

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务器会将 `/api` 代理到 `http://localhost:8000`。

## 原生部署

推荐直接使用一键部署脚本：

```bash
sudo bash deploy/install-native.sh
sudo systemctl daemon-reload
sudo systemctl restart claw-manager.service
```

服务器需要预先安装：`python3`、`venv`、`npm`、`systemd`、`sudo`，以及可执行的 OpenClaw / Nanobot 二进制。

脚本会完成代码同步、前后端安装、环境文件生成、`systemd` 单元安装和管理器启动。完整说明见 [`deploy/systemd/README.md`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy/systemd/README.md)。

如果 OpenClaw / Nanobot 二进制不在默认位置，可以在执行时覆盖变量：

```bash
sudo OPENCLAW_BIN=/opt/openclaw/bin/openclaw \
  NANOBOT_BIN=/opt/nanobot/bin/nanobot \
  MANAGER_PORT=8080 \
  bash deploy/install-native.sh
```

默认情况下，脚本会直接使用执行 `sudo bash deploy/install-native.sh` 的当前登录账户作为 `APP_USER`，不需要再手动传 `APP_USER` / `APP_GROUP`。如果 OpenClaw / Nanobot 就装在这个用户的 `~/.local/bin`，直接执行安装即可。

只有在你想显式指定另一个账户时，才需要传：

```bash
sudo env \
  APP_USER=leechen \
  APP_GROUP=leechen \
  OPENCLAW_BIN=/home/leechen/.local/bin/openclaw \
  NANOBOT_BIN=/home/leechen/.local/bin/nanobot \
  bash deploy/install-native.sh
```

如果你没有显式传入 `OPENCLAW_BIN` 或 `NANOBOT_BIN`，脚本会优先尝试从 `APP_USER` 的以下位置自动探测二进制：

- `~/.npm-global/bin`
- `~/.local/bin`
- 该用户登录 shell 的 `PATH`

如果你直接运行 `sudo bash deploy/install-native.sh` 且当前终端可交互，脚本在遇到二进制权限或路径问题时，会直接提示你输入修正值，而不是要求你退出后重新拼一串长 `env`。

首次成功执行后，后续直接运行：

```bash
sudo bash deploy/install-native.sh
```

脚本会继续复用上一次保存的 workspace 根目录和二进制路径配置；`APP_USER` / `APP_GROUP` 默认每次都取当前 `sudo` 调用者。如果检测到旧默认目录 `/srv/claw/workspaces` 仍在使用，脚本会自动迁移或合并到服务用户 home 下的新 `~/claw` 目录；只有同一个 `<owner>/<slug>` 在新旧目录两边都存在时，才需要手工处理冲突。如果这次执行的 `sudo` 调用者和上一次不同，脚本也会把旧 `<old_app_home>/claw` 自动迁到新的 `<new_app_home>/claw`。

如果只是修正 OpenClaw / Nanobot 二进制路径，通常更新 `/etc/claw-workspace-manager.env` 后直接重启对应 runtime service 即可；只有修改 `APP_USER`、`APP_GROUP` 或 unit 模板时才需要重新运行安装脚本并 `daemon-reload`。

关键环境变量：

- `APP_USER`：管理器服务用户，默认是当前 `sudo` 调用者；只有无法识别当前登录账户时才回退到 `claw-manager`
- `APP_GROUP`：管理器服务组，默认取 `APP_USER` 的主组
- `SQLITE_PATH`：SQLite 数据库路径
- `WORKSPACE_ROOT`：管理器读取 workspace 的本地路径
- `HOST_WORKSPACE_ROOT`：workspace 宿主机根目录
- `RUNTIME_STATE_ROOT`：运行时配置输出目录
- `WORKSPACE_TEMPLATE_ROOT`：基础 workspace 模板目录
- `OPENCLAW_WORKSPACE_TEMPLATE_ROOT`：OpenClaw workspace 模板目录
- `SYSTEMCTL_COMMAND`：管理器调用的 `systemctl` 命令
- `SYSTEMCTL_USE_SUDO`：是否通过 `sudo` 调用 `systemctl`
- `NANOBOT_UNIT_TEMPLATE`：Nanobot 模板单元名，默认 `claw-nanobot@{workspace_id}.service`
- `OPENCLAW_SHARED_UNIT`：OpenClaw 共享单元名，默认 `claw-openclaw.service`

## 服务器常用运维命令

查看管理器与运行时状态：

```bash
sudo systemctl status claw-manager.service
sudo systemctl status claw-openclaw.service
sudo systemctl status "claw-nanobot@<workspace_id>.service"
```

重启服务：

```bash
sudo systemctl restart claw-manager.service
sudo systemctl restart claw-openclaw.service
sudo systemctl restart "claw-nanobot@<workspace_id>.service"
```

停止 / 启动基础工作区实例：

```bash
sudo systemctl stop "claw-nanobot@<workspace_id>.service"
sudo systemctl start "claw-nanobot@<workspace_id>.service"
```

跟踪日志：

```bash
sudo journalctl -u claw-manager.service -f
sudo journalctl -u claw-openclaw.service -f
sudo journalctl -u "claw-nanobot@<workspace_id>.service" -f
```

检查环境文件与运行时配置：

```bash
sudo cat /etc/claw-workspace-manager.env
sudo cat /srv/claw/runtime/openclaw/openclaw.json
sudo cat "/srv/claw/runtime/nanobot/<workspace_id>/config.json"
sudo cat "/srv/claw/runtime/nanobot/<workspace_id>/runtime.env"
```

修改了 `systemd` 单元后重新加载：

```bash
sudo systemctl daemon-reload
sudo systemctl restart claw-manager.service
```

## 工作区目录约定

- 开发环境默认工作区根目录是 `backend/.data/workspaces`
- 每个工作区目录格式是 `<workspace_root>/<owner_user_id>/<slug>`
- `owner_user_id` 是所属用户 ID，不是工作区 ID
- `slug` 由工作区名称规范化生成；如果结果为空，则回退为 `workspace`

原生部署下，`<workspace_root>` 的默认值现在是服务用户 home 下的 `~/claw`。通常它会直接落到当前 `sudo` 调用者的 home，例如 `leechen` 执行安装时就是 `/home/leechen/claw`；只有在无法识别当前登录账户，或你显式指定 `APP_USER=claw-manager` 时，才会使用 `/opt/claw-workspace-manager/home/claw`。

例如：

- `backend/.data/workspaces/1/lee`
- `backend/.data/workspaces/1/workspace`

这样定义是为了按用户分层隔离、避免重名冲突，并在用户名变更后保持路径稳定。
