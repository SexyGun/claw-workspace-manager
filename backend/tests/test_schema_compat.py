from __future__ import annotations

from sqlalchemy import create_engine, text

from app.schema_compat import ensure_sqlite_schema_compatibility


def test_sqlite_schema_compatibility_adds_openclaw_columns_and_table(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE workspaces (
                    id INTEGER PRIMARY KEY,
                    owner_user_id INTEGER NOT NULL,
                    name VARCHAR(128) NOT NULL,
                    slug VARCHAR(128) NOT NULL,
                    host_path VARCHAR(512) NOT NULL,
                    template_version VARCHAR(64) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    created_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE workspace_configs (
                    workspace_id INTEGER PRIMARY KEY,
                    channel_config_json JSON NOT NULL,
                    gateway_config_json JSON NOT NULL,
                    nanobot_rendered_at DATETIME,
                    gateway_rendered_at DATETIME
                )
                """
            )
        )

    ensure_sqlite_schema_compatibility(engine)

    with engine.connect() as connection:
        workspace_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(workspaces)")).fetchall()}
        config_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(workspace_configs)")).fetchall()}
        tables = {row[0] for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}

    assert "workspace_type" in workspace_columns
    assert "openclaw_config_json" in config_columns
    assert "openclaw_rendered_at" in config_columns
    assert "openclaw_instances" in tables
