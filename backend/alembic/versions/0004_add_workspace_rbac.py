"""Add workspace and RBAC support for multi-tenant architecture

Revision ID: 0004_add_workspace_rbac
Revises: 0003_add_routing_config
Create Date: 2026-04-08 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_workspace_rbac"
down_revision = "0003_add_routing_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create workspaces table
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspaces_id", "workspaces", ["id"], unique=False)
    op.create_index("ix_workspaces_name", "workspaces", ["name"], unique=False)
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"], unique=False)
    op.create_index("ix_workspaces_created_at", "workspaces", ["created_at"], unique=False)
    
    # Create workspace_users table (junction table for RBAC)
    op.create_table(
        "workspace_users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspace_users_id", "workspace_users", ["id"], unique=False)
    op.create_index("ix_workspace_users_user_id", "workspace_users", ["user_id"], unique=False)
    op.create_index("ix_workspace_users_workspace_id", "workspace_users", ["workspace_id"], unique=False)
    
    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_id", "api_keys", ["id"], unique=False)
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)
    op.create_index("ix_api_keys_workspace_id", "api_keys", ["workspace_id"], unique=False)
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_created_at", "api_keys", ["created_at"], unique=False)
    
    # Add workspace_id columns to existing tables
    op.add_column("workflows", sa.Column("workspace_id", sa.String(), nullable=True))
    op.add_column("workflows", sa.Column("created_by", sa.String(), nullable=True))
    
    op.add_column("tasks", sa.Column("workspace_id", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("executed_by", sa.String(), nullable=True))
    
    # Add user context to audit logs
    op.add_column("audit_logs", sa.Column("user_id", sa.String(), nullable=True))
    op.add_column("audit_logs", sa.Column("workspace_id", sa.String(), nullable=True))
    
    # Create indexes for workspace filtering
    op.create_index("ix_workflows_workspace_id", "workflows", ["workspace_id"], unique=False)
    op.create_index("ix_workflows_created_by", "workflows", ["created_by"], unique=False)
    op.create_index("ix_tasks_workspace_id", "tasks", ["workspace_id"], unique=False)
    op.create_index("ix_tasks_executed_by", "tasks", ["executed_by"], unique=False)
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"], unique=False)


def downgrade() -> None:
    # Drop audit log indexes
    op.drop_index("ix_audit_logs_workspace_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    
    # Drop task indexes
    op.drop_index("ix_tasks_executed_by", table_name="tasks")
    op.drop_index("ix_tasks_workspace_id", table_name="tasks")
    
    # Drop workflow indexes
    op.drop_index("ix_workflows_created_by", table_name="workflows")
    op.drop_index("ix_workflows_workspace_id", table_name="workflows")
    
    # Drop columns from existing tables
    op.drop_column("audit_logs", "workspace_id")
    op.drop_column("audit_logs", "user_id")
    op.drop_column("tasks", "executed_by")
    op.drop_column("tasks", "workspace_id")
    op.drop_column("workflows", "created_by")
    op.drop_column("workflows", "workspace_id")
    
    # Drop API keys table
    op.drop_index("ix_api_keys_created_at", table_name="api_keys")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_workspace_id", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_index("ix_api_keys_id", table_name="api_keys")
    op.drop_table("api_keys")
    
    # Drop workspace users table
    op.drop_index("ix_workspace_users_workspace_id", table_name="workspace_users")
    op.drop_index("ix_workspace_users_user_id", table_name="workspace_users")
    op.drop_index("ix_workspace_users_id", table_name="workspace_users")
    op.drop_table("workspace_users")
    
    # Drop workspaces table
    op.drop_index("ix_workspaces_created_at", table_name="workspaces")
    op.drop_index("ix_workspaces_organization_id", table_name="workspaces")
    op.drop_index("ix_workspaces_name", table_name="workspaces")
    op.drop_index("ix_workspaces_id", table_name="workspaces")
    op.drop_table("workspaces")
