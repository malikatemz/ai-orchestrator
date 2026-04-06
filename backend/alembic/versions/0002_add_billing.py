"""Add billing tables for Stripe integration

Revision ID: 0002_add_billing
Revises: 0001_initial
Create Date: 2026-04-06 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_billing"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("subscription_plan", sa.String(), nullable=False, server_default="starter"),
        sa.Column("subscription_status", sa.String(), nullable=False, server_default="trialing"),
        sa.Column("subscription_item_id", sa.String(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("billing_cycle_anchor", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(op.f("ix_organizations_email"), "organizations", ["email"], unique=True)
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"], unique=False)
    op.create_index(op.f("ix_organizations_stripe_customer_id"), "organizations", ["stripe_customer_id"], unique=True)
    op.create_index(op.f("ix_organizations_subscription_status"), "organizations", ["subscription_status"], unique=False)
    op.create_index(op.f("ix_organizations_created_at"), "organizations", ["created_at"], unique=False)

    # Create usage_records table
    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("usage_type", sa.String(), nullable=False, server_default="task_execution"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.Text(), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usage_records_id"), "usage_records", ["id"], unique=False)
    op.create_index(op.f("ix_usage_records_org_id"), "usage_records", ["org_id"], unique=False)
    op.create_index(op.f("ix_usage_records_task_id"), "usage_records", ["task_id"], unique=False)
    op.create_index(op.f("ix_usage_records_usage_type"), "usage_records", ["usage_type"], unique=False)
    op.create_index(op.f("ix_usage_records_created_at"), "usage_records", ["created_at"], unique=False)


def downgrade() -> None:
    # Drop usage_records table
    op.drop_index(op.f("ix_usage_records_created_at"), table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_usage_type"), table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_task_id"), table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_org_id"), table_name="usage_records")
    op.drop_index(op.f("ix_usage_records_id"), table_name="usage_records")
    op.drop_table("usage_records")

    # Drop organizations table
    op.drop_index(op.f("ix_organizations_created_at"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_subscription_status"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_stripe_customer_id"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_email"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_table("organizations")
