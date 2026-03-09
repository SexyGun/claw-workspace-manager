# 原生运行时部署

本目录提供 OpenClaw 共享服务和 Nanobot 单工作区服务的 `systemd` 模板。

## 目录约定

- 工作区目录：`/srv/claw/workspaces/<owner_user_id>/<slug>`
- 运行时目录：`/srv/claw/runtime`
- OpenClaw 聚合配置：`/srv/claw/runtime/openclaw/openclaw.json`
- Nanobot 单工作区配置：`/srv/claw/runtime/nanobot/<workspace_id>/gateway.yaml`

## 安装步骤

1. 将 `claw-openclaw.service` 和 `claw-nanobot@.service` 复制到 `/etc/systemd/system/`。
2. 按实际安装位置修改 `OPENCLAW_BIN`、`NANOBOT_GATEWAY_BIN`、`CLAW_RUNTIME_ROOT`。
3. 执行 `systemctl daemon-reload`。
4. 按需启用共享 OpenClaw 服务：

   ```bash
   systemctl enable --now claw-openclaw.service
   ```

5. Nanobot 工作区实例由管理器通过 `claw-nanobot@<workspace_id>.service` 动态控制。

## sudoers

如果管理器进程不是 root，请参考 `deploy/sudoers/claw-workspace-manager` 添加受限 `sudo` 权限，只允许：

- `start/stop/restart/status/reload claw-openclaw.service`
- `start/stop/restart/status claw-nanobot@<workspace_id>.service`

## 注意

- OpenClaw 采用单共享服务，多 workspace 通过聚合配置里的 `agents.list` 和 `bindings` 生效。
- Nanobot 采用每工作区一个实例，端口由管理器分配并写入运行时目录。
- `ExecStart` 需要根据你服务器上的真实二进制命令调整；模板里的命令只是推荐形状。
