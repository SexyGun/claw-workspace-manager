# 原生运行时部署

默认入口是仓库根目录下的 `deploy/install-native.sh`。脚本会完成：

- 创建 `claw-manager` 系统用户
- 同步代码到 `/opt/claw-workspace-manager/app`
- 创建 Python 虚拟环境并安装后端依赖
- 构建前端并发布到 `backend/app/static`
- 生成 `/etc/claw-workspace-manager.env`
- 安装 `claw-manager.service`、`claw-openclaw.service`、`claw-nanobot@.service`
- 安装受限 `sudoers`
- 启动管理器服务

## 一键部署

在服务器上克隆仓库后执行：

```bash
sudo bash deploy/install-native.sh
```

服务器需要预先具备：`python3`、`venv`、`npm`、`systemd`、`sudo`，以及 OpenClaw / Nanobot 的可执行文件。

如果你的 OpenClaw / Nanobot 二进制不在默认位置，可以直接覆盖环境变量：

```bash
sudo OPENCLAW_BIN=/opt/openclaw/bin/openclaw \
  NANOBOT_BIN=/opt/nanobot/bin/nanobot \
  MANAGER_PORT=8080 \
  bash deploy/install-native.sh
```

如果二进制安装在某个已有登录用户的 `~/.local/bin`，运行时 unit 应该直接切到这个用户，并显式传入该用户的 `HOME`：

```bash
sudo env \
  RUNTIME_USER=leechen \
  RUNTIME_HOME=/home/leechen \
  OPENCLAW_BIN=/home/leechen/.local/bin/openclaw \
  NANOBOT_BIN=/home/leechen/.local/bin/nanobot \
  bash deploy/install-native.sh
```

如果你已经指定了 `RUNTIME_USER` / `RUNTIME_HOME`，脚本会在未显式传入 `OPENCLAW_BIN` / `NANOBOT_BIN` 时自动尝试从 `~/.npm-global/bin`、`~/.local/bin` 以及该用户登录 shell 的 `PATH` 中发现二进制。

在交互式终端中直接运行 `sudo bash deploy/install-native.sh` 时，如果 runtime 用户、`HOME` 或二进制可执行权限不正确，脚本会现场提示并要求输入修正值。

这些变量会写入 `/etc/claw-workspace-manager.env`。首次成功设置后，后续直接重新执行：

```bash
sudo bash deploy/install-native.sh
```

脚本会自动复用上一次的 runtime 用户、`HOME` 和二进制路径。

OpenClaw / Nanobot 的二进制路径现在由 `/etc/claw-workspace-manager.env` 提供给 runtime unit；如果只是修正 `OPENCLAW_BIN` 或 `NANOBOT_BIN`，通常编辑 env 文件后直接重启对应 service 即可，不必重写 unit。若修改了 `RUNTIME_USER` / `RUNTIME_GROUP`，仍需要重新运行安装脚本并执行 `systemctl daemon-reload`。

## 默认目录

- 应用目录：`/opt/claw-workspace-manager/app`
- 虚拟环境：`/opt/claw-workspace-manager/venv`
- 管理器环境文件：`/etc/claw-workspace-manager.env`
- 工作区目录：`/srv/claw/workspaces/<owner_user_id>/<slug>`
- 运行时目录：`/srv/claw/runtime`
- OpenClaw 聚合配置：`/srv/claw/runtime/openclaw/openclaw.json`
- Nanobot 单工作区配置：`/srv/claw/runtime/nanobot/<workspace_id>/config.json`
- Nanobot 单工作区环境文件：`/srv/claw/runtime/nanobot/<workspace_id>/runtime.env`

## 手工调整

脚本安装后的 `systemd` 单元来自本目录中的三份模板：

- `claw-manager.service`
- `claw-openclaw.service`
- `claw-nanobot@.service`

如果你需要更换运行用户、安装目录或二进制路径，可以修改这些模板后重新运行脚本，或者直接修改 `/etc/systemd/system/` 下的已安装单元并执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart claw-manager.service
```

运行时相关变量：

- `APP_USER` / `APP_GROUP`：管理器服务用户和组
- `RUNTIME_USER` / `RUNTIME_GROUP`：OpenClaw / Nanobot runtime unit 使用的用户和组
- `RUNTIME_HOME`：runtime unit 的 `HOME`
- `OPENCLAW_BIN` / `NANOBOT_BIN`：对应 runtime 二进制路径

## sudoers

如果你不使用默认的 `claw-manager` 用户，请同步调整 `deploy/sudoers/claw-workspace-manager`，或直接重新运行脚本让它按当前变量重写 `/etc/sudoers.d/claw-workspace-manager`。

## 注意

- OpenClaw 采用单共享服务，多 workspace 通过聚合配置里的 `agents.list` 和 `bindings` 生效。
- OpenClaw 共享服务通过 `OPENCLAW_CONFIG_PATH` 指向聚合配置文件，然后执行 `openclaw gateway`。
- Nanobot 采用每工作区一个原生实例，`systemd` 通过实例目录内的 `runtime.env` 启动 `nanobot gateway --config ...`。
- 当 `RUNTIME_USER` 与 `APP_USER` 不同时，安装脚本会把 `/srv/claw` 调整为共享组可写，并让运行时 unit 继承 `RUNTIME_HOME`。
- 一键部署脚本只负责安装管理器，不负责下载 OpenClaw / Nanobot 二进制本身。
