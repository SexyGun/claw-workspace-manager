# Claw 工作区管理器

面向单台 Linux 主机的容器化多用户工作区管理器。

## 技术栈

- 后端：FastAPI、SQLAlchemy 2、SQLite、Alembic
- 前端：Vue 3、Vite、TypeScript、Naive UI
- 运行环境：Docker Compose，包含一个管理容器和按工作区划分的网关容器

## 功能特性

- 本地用户名/密码认证，支持 `admin` 和 `user` 角色
- 管理员统一管理用户生命周期
- 每个用户可拥有多个工作区
- 支持基础工作区和 OpenClaw 工作区两种类型
- 通过服务端模板目录初始化工作区
- 自动生成 `.nanobot/config.json` 和 `.nanobot/gateway.yaml`
- 自动生成 `.openclaw/openclaw.json`，支持原始文本与结构化两种编辑方式
- 基于 Docker 的 Gateway 与 OpenClaw 运行时启停、重启和状态跟踪

## 仓库结构

- [`backend`](/Users/lichen/zh_workplace/claw-workspace-manager/backend) FastAPI 应用、数据库模型、Alembic 和测试
- [`frontend`](/Users/lichen/zh_workplace/claw-workspace-manager/frontend) Vue 管理控制台
- [`deploy`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy) Compose、入口脚本和模板文件

## 本地后端开发

1. 创建虚拟环境并安装后端包：

   ```bash
   cd backend
   python3 -m pip install -e .[dev]
   ```

2. 启动 API：

   ```bash
   export SESSION_SECRET=dev-secret
   export BOOTSTRAP_ADMIN_USERNAME=admin
   export BOOTSTRAP_ADMIN_PASSWORD=admin-password
   uvicorn app.main:app --reload
   ```

3. 运行后端测试：

   ```bash
   pytest
   ```

## 本地前端开发

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务器会将 `/api` 代理到 `http://localhost:8000`。

## Docker 部署

1. 将 [`deploy/.env.example`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy/.env.example) 复制为 `deploy/.env`，并按需修改配置。
2. 确保 `.env` 中引用的宿主机目录已经存在，且模板根目录包含 `base-workspace/`。
3. 启动管理服务：

   ```bash
   cd deploy
   docker compose --env-file .env up --build -d
   ```

4. 打开 `http://<host>:<MANAGER_PORT>`。

## 说明

- 管理容器需要访问 `/var/run/docker.sock`，因此只应部署在可信的单租户主机上。
- 当管理器请求 Docker 将工作区挂载进 Gateway 或 OpenClaw 运行容器时，会使用 `HOST_WORKSPACE_ROOT`。
- 当前运行流程默认 `GATEWAY_IMAGE` 和 `OPENCLAW_IMAGE` 已具备读取挂载配置文件并启动的能力。
