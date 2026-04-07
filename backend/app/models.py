from __future__ import annotations

import json
from enum import Enum

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Session, declarative_base, relationship

from .time_utils import utc_now

Base = declarative_base()


class UserRole(str, Enum):
    """User roles for RBAC."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    BILLING_ADMIN = "billing_admin"


class User(Base):
    """User model for authentication and authorization"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    picture_url = Column(String, nullable=True)
    oauth_provider = Column(String, nullable=True)  # 'google', 'github', etc.
    oauth_id = Column(String, nullable=True, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="users")


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    owner = Column(String, default="operations", nullable=False)
    status = Column(String, default="active", nullable=False)
    priority = Column(String, default="medium", nullable=False)
    target_model = Column(String, default="gpt-4.1-mini", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)

    tasks = relationship("Task", back_populates="workflow", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    source_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    agent = Column(String, default="planner", nullable=False)
    stage = Column(String, default="queued", nullable=False)
    status = Column(String, default="pending", nullable=False)
    queue_name = Column(String, default="default", nullable=False)
    input_data = Column(Text, nullable=False)
    output_data = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    retries = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    workflow = relationship("Workflow", back_populates="tasks")
    source_task = relationship("Task", remote_side=[id], uselist=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, nullable=False, default="system")
    event = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=False, index=True)
    resource_id = Column(Integer, nullable=True, index=True)
    details_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    @property
    def details(self) -> dict:
        try:
            return json.loads(self.details_json or "{}")
        except json.JSONDecodeError:
            return {}


class Organization(Base):
    """Organization with billing and subscription info"""
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    slug = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    stripe_customer_id = Column(String, nullable=True, unique=True, index=True)
    subscription_plan = Column(String, default="starter", nullable=False)
    subscription_status = Column(String, default="trialing", nullable=False, index=True)
    subscription_item_id = Column(String, nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    billing_cycle_anchor = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="organization", cascade="all, delete-orphan")


class UsageRecord(Base):
    """API usage tracking for billing"""
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    task_id = Column(Integer, nullable=True, index=True)
    usage_type = Column(String, default="task_execution", nullable=False, index=True)
    quantity = Column(Integer, default=1, nullable=False)
    metadata_json = Column(Text, nullable=True, default="{}")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    organization = relationship("Organization", back_populates="usage_records")

    @property
    def meta(self) -> dict:
        """Parse metadata JSON string into dictionary"""
        try:
            return json.loads(self.metadata_json or "{}")
        except json.JSONDecodeError:
            return {}


def count_records(db: Session, model) -> int:
    return db.query(model).count()


def build_engine(database_url: str):
    from .database import build_engine as database_build_engine

    return database_build_engine(database_url)


def build_session_factory(engine):
    from .database import build_session

    return build_session(engine)


def init_db(engine_override=None):
    from .database import init_db as database_init_db

    return database_init_db(engine_override)


from .database import SessionLocal, engine  # noqa: E402  # compatibility exports for tests
