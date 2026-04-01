import os
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ai_orchestrator.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
    name = Column(String, nullable=False)
    agent = Column(String, default="planner", nullable=False)
    stage = Column(String, default="queued", nullable=False)
    status = Column(String, default="pending", nullable=False)
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


Base.metadata.create_all(bind=engine)
