from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session, declarative_base, relationship

Base = declarative_base()


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=False)
    owner = Column(String, default="operations", nullable=False)
    status = Column(String, default="active", nullable=False)
    priority = Column(String, default="medium", nullable=False)
    target_model = Column(String, default="gpt-4.1-mini", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_run_at = Column(DateTime, nullable=True)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    @property
    def details(self) -> dict:
        try:
            return json.loads(self.details_json or "{}")
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
