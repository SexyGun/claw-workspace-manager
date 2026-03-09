"""add openclaw workspace support"""

from alembic import op
import sqlalchemy as sa


revision = "0002_openclaw_workspace_type"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("workspace_type", sa.String(length=32), nullable=False, server_default="base"),
    )
    op.add_column(
        "workspace_configs",
        sa.Column("openclaw_config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "workspace_configs",
        sa.Column("openclaw_rendered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "openclaw_instances",
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("container_name", sa.String(length=255), nullable=False),
        sa.Column("image", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("last_container_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("openclaw_instances")
    op.drop_column("workspace_configs", "openclaw_rendered_at")
    op.drop_column("workspace_configs", "openclaw_config_json")
    op.drop_column("workspaces", "workspace_type")
