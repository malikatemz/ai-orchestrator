"""Add routing configuration columns to workflows and provider tracking to tasks

Revision ID: 0003_add_routing_config
Revises: 0002_add_billing
Create Date: 2026-04-07 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_routing_config"
down_revision = "0002_add_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add routing configuration columns to workflows table
    op.add_column("workflows", sa.Column("routing_strategy", sa.String(), nullable=False, server_default="balanced"))
    op.add_column("workflows", sa.Column("fallback_chain", sa.Text(), nullable=True))
    op.add_column("workflows", sa.Column("cost_threshold", sa.Float(), nullable=False, server_default="10.0"))
    op.add_column("workflows", sa.Column("latency_threshold_ms", sa.Integer(), nullable=False, server_default="30000"))
    op.add_column("workflows", sa.Column("prefer_providers", sa.Text(), nullable=True))
    
    # Add provider execution tracking columns to tasks table
    op.add_column("tasks", sa.Column("executed_provider", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("execution_cost_usd", sa.Float(), nullable=True))
    op.add_column("tasks", sa.Column("execution_latency_ms", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("tokens_used", sa.Integer(), nullable=True))
    
    # Create indexes for executed_provider and cost columns for analytics queries
    op.create_index("ix_tasks_executed_provider", "tasks", ["executed_provider"], unique=False)
    op.create_index("ix_tasks_execution_cost_usd", "tasks", ["execution_cost_usd"], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_tasks_execution_cost_usd", table_name="tasks")
    op.drop_index("ix_tasks_executed_provider", table_name="tasks")
    
    # Drop provider tracking columns from tasks
    op.drop_column("tasks", "tokens_used")
    op.drop_column("tasks", "execution_latency_ms")
    op.drop_column("tasks", "execution_cost_usd")
    op.drop_column("tasks", "executed_provider")
    
    # Drop routing configuration columns from workflows
    op.drop_column("workflows", "prefer_providers")
    op.drop_column("workflows", "latency_threshold_ms")
    op.drop_column("workflows", "cost_threshold")
    op.drop_column("workflows", "fallback_chain")
    op.drop_column("workflows", "routing_strategy")
