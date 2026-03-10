# 原生运行时部署

默认入口是仓库根目录下的 `deploy/install-native.sh`。脚本会完成：

- 默认使用当前 `sudo` 调用者作为服务用户；只有在无法识别当前登录账户时才创建 `claw-manager` 系统用户
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

如果你没有显式传入 `OPENCLAW_BIN` / `NANOBOT_BIN`，脚本会在 `APP_USER` 的 `~/.npm-global/bin`、`~/.local/bin` 以及该用户登录 shell 的 `PATH` 中自动尝试发现二进制。

在交互式终端中直接运行 `sudo bash deploy/install-native.sh` 时，如果二进制可执行权限或路径不正确，脚本会现场提示并要求输入修正值。

这些变量会写入 `/etc/claw-workspace-manager.env`。首次成功设置后，后续直接重新执行：

```bash
sudo bash deploy/install-native.sh
```

脚本会继续复用上一次保存的 `DATA_ROOT` / workspace 根目录和二进制路径；`APP_USER` / `APP_GROUP` 默认每次都取当前 `sudo` 调用者。现在默认的数据根、workspace 根、SQLite 路径和 runtime 状态目录都会一起落在服务用户 home 下的 `~/claw`。如果检测到旧默认目录 `/srv/claw` 仍在使用，脚本会自动把其中的 `workspaces`、`runtime`、`sqlite` 迁移或合并到新的 `~/claw`；只有同一个 `<owner>/<slug>` 在新旧目录两边都存在时，才需要手工处理冲突。如果这次执行的 `sudo` 调用者和上一次不同，脚本也会把旧 `<old_app_home>/claw` 自动迁到新的 `<new_app_home>/claw`。

OpenClaw / Nanobot 的二进制路径现在由 `/etc/claw-workspace-manager.env` 提供给 runtime unit；如果只是修正 `OPENCLAW_BIN` 或 `NANOBOT_BIN`，通常编辑 env 文件后直接重启对应 service 即可，不必重写 unit。若修改了 `APP_USER` / `APP_GROUP`，仍需要重新运行安装脚本并执行 `systemctl daemon-reload`。

## 默认目录

- 应用目录：`/opt/claw-workspace-manager/app`
- 虚拟环境：`/opt/claw-workspace-manager/venv`
- 管理器环境文件：`/etc/claw-workspace-manager.env`
- 数据根目录：`<app_user_home>/claw`
- 工作区目录：`<app_user_home>/claw/<owner_user_id>/<slug>`
- SQLite 数据库：`<app_user_home>/claw/sqlite/app.db`
- 运行时目录：`<app_user_home>/claw/runtime`
- OpenClaw 聚合配置：`<app_user_home>/claw/runtime/openclaw/openclaw.json`
- Nanobot 单工作区配置：`<app_user_home>/claw/runtime/nanobot/<workspace_id>/config.json`
- Nanobot 单工作区环境文件：`<app_user_home>/claw/runtime/nanobot/<workspace_id>/runtime.env`

通常 `APP_USER` 会直接取当前 `sudo` 调用者，因此 `leechen` 执行安装时，`<app_user_home>` 就是 `/home/leechen`，默认数据根和工作区根目录都会是 `/home/leechen/claw`。只有在无法识别当前登录账户，或你显式指定 `APP_USER=claw-manager` 时，才会使用 `/opt/claw-workspace-manager/home/claw`。

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

- `APP_USER` / `APP_GROUP`：管理器服务用户和组，默认取当前 `sudo` 调用者及其主组
- `RUNTIME_USER` / `RUNTIME_GROUP` / `RUNTIME_HOME`：由安装脚本按 `APP_USER` 的 home 自动生成，不再支持与 manager 分离
- `OPENCLAW_BIN` / `NANOBOT_BIN`：对应 runtime 二进制路径

## sudoers

如果你手工修改了 `deploy/sudoers/claw-workspace-manager` 模板，请在调整服务用户后重新运行脚本，让它按当前变量重写 `/etc/sudoers.d/claw-workspace-manager`。

## 注意

- OpenClaw 采用单共享服务，多 workspace 通过聚合配置里的 `agents.list` 和 `bindings` 生效。
- OpenClaw 共享服务通过 `OPENCLAW_CONFIG_PATH` 指向聚合配置文件，然后执行 `openclaw gateway`。
- Nanobot 采用每工作区一个原生实例，`systemd` 通过实例目录内的 `runtime.env` 启动 `nanobot gateway --config ...`。
- 旧版本默认把数据放在 `/srv/claw`，其中工作区位于 `/srv/claw/workspaces`；重新运行安装脚本时，脚本会自动把 `workspaces`、`runtime`、`sqlite` 迁移或合并到新的 `~/claw`。
- 一键部署脚本只负责安装管理器，不负责下载 OpenClaw / Nanobot 二进制本身。
