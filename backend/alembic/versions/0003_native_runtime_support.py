"""add native runtime support"""

from alembic import op
import sqlalchemy as sa


revision = "0003_native_runtime_support"
down_revision = "0002_openclaw_workspace_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspace_configs",
        sa.Column("openclaw_channel_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "workspace_configs",
        sa.Column("openclaw_binding_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_table(
        "workspace_runtimes",
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("runtime_kind", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("controller_kind", sa.String(length=32), nullable=False),
        sa.Column("unit_name", sa.String(length=255), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=True),
        sa.Column("listen_port", sa.Integer(), nullable=True, unique=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("needs_restart", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "shared_runtimes",
        sa.Column("runtime_key", sa.String(length=64), primary_key=True),
        sa.Column("runtime_kind", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("controller_kind", sa.String(length=32), nullable=False),
        sa.Column("unit_name", sa.String(length=255), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("needs_restart", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("shared_runtimes")
    op.drop_table("workspace_runtimes")
    op.drop_column("workspace_configs", "openclaw_binding_json")
    op.drop_column("workspace_configs", "openclaw_channel_json")
