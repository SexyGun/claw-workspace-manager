# Claw Workspace Manager

Dockerized multi-user workspace manager for a single Linux host.

## Stack

- Backend: FastAPI, SQLAlchemy 2, SQLite, Alembic
- Frontend: Vue 3, Vite, TypeScript, Naive UI
- Runtime: Docker Compose with one manager container and per-workspace gateway containers

## Features

- Local username/password authentication with `admin` and `user` roles
- Admin-managed user lifecycle
- Multiple workspaces per user
- Workspace bootstrap from a server-side template directory
- Generated `.nanobot/config.json` and `.nanobot/gateway.yaml`
- Docker-based gateway start, stop, restart, and status tracking

## Repository Layout

- [`backend`](/Users/lichen/zh_workplace/claw-workspace-manager/backend) FastAPI application, database models, Alembic, and tests
- [`frontend`](/Users/lichen/zh_workplace/claw-workspace-manager/frontend) Vue admin console
- [`deploy`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy) Compose, entrypoint, and template files

## Local Backend Development

1. Create a virtualenv and install the backend package:

   ```bash
   cd backend
   python3 -m pip install -e .[dev]
   ```

2. Run the API:

   ```bash
   export SESSION_SECRET=dev-secret
   export BOOTSTRAP_ADMIN_USERNAME=admin
   export BOOTSTRAP_ADMIN_PASSWORD=admin-password
   uvicorn app.main:app --reload
   ```

3. Run backend tests:

   ```bash
   pytest
   ```

## Local Frontend Development

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

## Docker Deployment

1. Copy [`deploy/.env.example`](/Users/lichen/zh_workplace/claw-workspace-manager/deploy/.env.example) to `deploy/.env` and adjust values.
2. Ensure the host directories from `.env` exist and that the template root contains `base-workspace/`.
3. Start the manager:

   ```bash
   cd deploy
   docker compose --env-file .env up --build -d
   ```

4. Open `http://<host>:<MANAGER_PORT>`.

## Notes

- The manager container needs access to `/var/run/docker.sock`, so deploy it only on a trusted single-tenant host.
- `HOST_WORKSPACE_ROOT` is used when the manager asks Docker to mount a workspace into a gateway container.
- The current gateway flow assumes the configured `GATEWAY_IMAGE` already knows how to start using the mounted config files.
