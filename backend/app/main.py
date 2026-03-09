from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth, users, workspaces
from app.config import get_settings
from app.constants import USER_ROLE_ADMIN
from app.db import Base, SessionLocal, engine
from app.models import User
from app.services.auth import create_user
from app.services.gateway import build_gateway_manager
from app.services.openclaw_runtime import build_openclaw_runtime_manager
from app.services.workspace import ensure_workspace_roots


def ensure_bootstrap_admin() -> None:
    settings = get_settings()
    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        return
    db = SessionLocal()
    try:
        admin_exists = db.scalar(select(User).where(User.role == USER_ROLE_ADMIN))
        if not admin_exists:
            create_user(
                db,
                settings.bootstrap_admin_username,
                settings.bootstrap_admin_password,
                USER_ROLE_ADMIN,
                True,
            )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_workspace_roots(settings)
    Base.metadata.create_all(bind=engine)
    ensure_bootstrap_admin()
    gateway_manager = build_gateway_manager(settings)
    openclaw_manager = build_openclaw_runtime_manager(settings)
    db = SessionLocal()
    try:
        gateway_manager.sync_managed_containers(db)
        openclaw_manager.sync_managed_containers(db)
    finally:
        db.close()
    app.state.gateway_manager = gateway_manager
    app.state.openclaw_manager = openclaw_manager
    yield


app = FastAPI(title="Claw Workspace Manager", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.app_env == "production",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(workspaces.workspace_type_router, prefix=settings.api_prefix)
app.include_router(workspaces.router, prefix=settings.api_prefix)


@app.get(f"{settings.api_prefix}/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


static_dir = Path(__file__).parent / "static"
assets_dir = static_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
async def index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend build not found. Run the frontend build first."}, status_code=503)


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_handler(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    target = static_dir / full_path
    if target.exists() and target.is_file():
        return FileResponse(target)
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend build not found. Run the frontend build first."}, status_code=503)
