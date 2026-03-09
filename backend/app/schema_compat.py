from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def ensure_sqlite_schema_compatibility(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    with engine.begin() as connection:
        if _table_exists(inspector, "workspaces"):
            workspace_columns = _column_names(inspector, "workspaces")
            if "workspace_type" not in workspace_columns:
                connection.execute(
                    text("ALTER TABLE workspaces ADD COLUMN workspace_type VARCHAR(32) NOT NULL DEFAULT 'base'")
                )

        inspector = inspect(connection)
        if _table_exists(inspector, "workspace_configs"):
            config_columns = _column_names(inspector, "workspace_configs")
            if "openclaw_config_json" not in config_columns:
                connection.execute(
                    text("ALTER TABLE workspace_configs ADD COLUMN openclaw_config_json JSON NOT NULL DEFAULT '{}'")
                )
            if "openclaw_channel_json" not in config_columns:
                connection.execute(
                    text("ALTER TABLE workspace_configs ADD COLUMN openclaw_channel_json JSON NOT NULL DEFAULT '{}'")
                )
            if "openclaw_binding_json" not in config_columns:
                connection.execute(
                    text("ALTER TABLE workspace_configs ADD COLUMN openclaw_binding_json JSON NOT NULL DEFAULT '{}'")
                )
            if "openclaw_rendered_at" not in config_columns:
                connection.execute(text("ALTER TABLE workspace_configs ADD COLUMN openclaw_rendered_at DATETIME NULL"))

        inspector = inspect(connection)
        if not _table_exists(inspector, "workspace_runtimes"):
            connection.execute(
                text(
                    """
                    CREATE TABLE workspace_runtimes (
                        workspace_id INTEGER NOT NULL PRIMARY KEY,
                        runtime_kind VARCHAR(32) NOT NULL,
                        scope VARCHAR(32) NOT NULL,
                        controller_kind VARCHAR(32) NOT NULL,
                        unit_name VARCHAR(255) NOT NULL,
                        process_id INTEGER,
                        listen_port INTEGER UNIQUE,
                        state VARCHAR(32) NOT NULL,
                        last_error TEXT,
                        started_at DATETIME,
                        stopped_at DATETIME,
                        needs_restart BOOLEAN NOT NULL DEFAULT 0,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
                    )
                    """
                )
            )

        inspector = inspect(connection)
        if not _table_exists(inspector, "shared_runtimes"):
            connection.execute(
                text(
                    """
                    CREATE TABLE shared_runtimes (
                        runtime_key VARCHAR(64) NOT NULL PRIMARY KEY,
                        runtime_kind VARCHAR(32) NOT NULL,
                        scope VARCHAR(32) NOT NULL,
                        controller_kind VARCHAR(32) NOT NULL,
                        unit_name VARCHAR(255) NOT NULL,
                        process_id INTEGER,
                        state VARCHAR(32) NOT NULL,
                        last_error TEXT,
                        started_at DATETIME,
                        stopped_at DATETIME,
                        needs_restart BOOLEAN NOT NULL DEFAULT 0
                    )
                    """
                )
            )
