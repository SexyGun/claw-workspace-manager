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
            if "openclaw_rendered_at" not in config_columns:
                connection.execute(text("ALTER TABLE workspace_configs ADD COLUMN openclaw_rendered_at DATETIME NULL"))

        inspector = inspect(connection)
        if not _table_exists(inspector, "openclaw_instances"):
            connection.execute(
                text(
                    """
                    CREATE TABLE openclaw_instances (
                        workspace_id INTEGER NOT NULL PRIMARY KEY,
                        container_name VARCHAR(255) NOT NULL,
                        image VARCHAR(255) NOT NULL,
                        state VARCHAR(32) NOT NULL,
                        last_container_id VARCHAR(255),
                        last_error TEXT,
                        started_at DATETIME,
                        stopped_at DATETIME,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
                    )
                    """
                )
            )
