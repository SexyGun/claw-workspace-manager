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
  NANOBOT_GATEWAY_BIN=/opt/nanobot/bin/nanobot-gateway \
  MANAGER_PORT=8080 \
  bash deploy/install-native.sh
```

## 默认目录

- 应用目录：`/opt/claw-workspace-manager/app`
- 虚拟环境：`/opt/claw-workspace-manager/venv`
- 管理器环境文件：`/etc/claw-workspace-manager.env`
- 工作区目录：`/srv/claw/workspaces/<owner_user_id>/<slug>`
- 运行时目录：`/srv/claw/runtime`
- OpenClaw 聚合配置：`/srv/claw/runtime/openclaw/openclaw.json`
- Nanobot 单工作区配置：`/srv/claw/runtime/nanobot/<workspace_id>/gateway.yaml`

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

## sudoers

如果你不使用默认的 `claw-manager` 用户，请同步调整 `deploy/sudoers/claw-workspace-manager`，或直接重新运行脚本让它按当前变量重写 `/etc/sudoers.d/claw-workspace-manager`。

## 注意

- OpenClaw 采用单共享服务，多 workspace 通过聚合配置里的 `agents.list` 和 `bindings` 生效。
- Nanobot 采用每工作区一个实例，端口由管理器分配并写入运行时目录。
- 一键部署脚本只负责安装管理器，不负责下载 OpenClaw / Nanobot 二进制本身。
