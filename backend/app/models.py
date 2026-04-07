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
    """User model for authentication and authorization.
    
    Represents a user account with OAuth integration, RBAC role assignments, and organization
    membership. Users authenticate via OAuth2 providers (Google, GitHub) or local password auth.
    Each user belongs to exactly one organization and can have multiple roles for fine-grained
    access control.
    
    Attributes:
        id: Unique user identifier (UUID or OAuth user ID)
        email: Email address (unique, indexed for fast lookup)
        full_name: Display name from OAuth provider or manual entry
        hashed_password: Bcrypt-hashed password (nullable for OAuth-only users)
        picture_url: Profile picture URL from OAuth provider
        oauth_provider: OAuth provider name ('google', 'github', etc.) or None for local auth
        oauth_id: OAuth provider's user ID (unique per provider)
        is_active: Soft delete flag (false = deactivated, true = active)
        is_admin: Platform admin flag (true = bypass all org-level permissions)
        role: RBAC role (owner/admin/member/viewer/billing_admin)
        org_id: Foreign key to Organization (nullable for pending org assignment)
        created_at: Account creation timestamp (UTC)
        updated_at: Last modification timestamp (UTC, auto-updated)
        last_login_at: Last successful login timestamp or None if never logged in
    
    Relationships:
        organization: Back-reference to parent Organization. Cascade: all, delete-orphan
            (user deletion cascades but org deletion does NOT delete users).
    
    Indexes:
        - email (unique): Fast email lookup for authentication
        - oauth_id (unique): Fast OAuth user lookup
        - org_id: Fast user lookup by organization
        - is_active: Soft delete filtering
    
    Example:
        >>> user = User(
        ...     id="user-abc123",
        ...     email="alice@example.com",
        ...     full_name="Alice Smith",
        ...     hashed_password="$2b$12$...",
        ...     role=UserRole.OWNER,
        ...     org_id="org-123"
        ... )
        >>> session.add(user)
        >>> session.commit()
        >>> user.organization.name
        'Acme Inc'
    """
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
    """Workflow orchestration model for multi-step AI task execution.
    
    A Workflow represents a reusable template for executing multi-step AI-assisted processes.
    It defines the DAG structure, target LLM model, and execution priority. Each workflow can be
    instantiated multiple times through Task records, allowing users to execute the same workflow
    with different inputs.
    
    Workflow Status States:
        active: Workflow is available for task execution (default)
        paused: No new tasks are accepted (scheduled maintenance)
        archived: Soft-deleted, visible in history but no new tasks
        draft: In-progress definition, not yet executable
    
    Attributes:
        id: Primary key (auto-increment integer)
        name: Workflow display name (indexed for search/sort)
        description: Long-form description of workflow purpose
        owner: User ID of workflow creator (default: "operations" for system workflows)
        status: Current workflow state (active/paused/archived/draft)
        priority: Default task priority (high/medium/low) - used when queueing tasks
        target_model: Default LLM model for this workflow (gpt-4.1-mini, claude-3-opus, etc.)
        created_at: Workflow creation timestamp (UTC, indexed)
        updated_at: Last modification timestamp (UTC, auto-updated)
        last_run_at: Most recent task completion timestamp, or None if never executed
    
    Relationships:
        tasks: One-to-Many relationship to Task records.
            Cascade: all, delete-orphan
            When workflow is deleted, all associated tasks are deleted automatically.
            Inverse: Task.workflow
    
    Indexes:
        - name: Fast workflow lookup by name
        - owner: Fast lookup of user's workflows
        - created_at: Chronological sorting
        - status: Quick filtering by state
    
    Example:
        >>> workflow = Workflow(
        ...     name="Email Summarizer",
        ...     description="Summarize incoming emails using Claude",
        ...     owner="user-123",
        ...     priority="high",
        ...     target_model="claude-3-opus-20240229"
        ... )
        >>> session.add(workflow)
        >>> session.commit()
        >>> task = Task(workflow_id=workflow.id, name="Summarize inbox")
        >>> session.add(task)
    """
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
    """Task execution record for a workflow instance.
    
    A Task represents a single execution instance of a Workflow. It tracks the complete
    execution lifecycle from submission through completion, including input data, output results,
    error messages, and retry history. Tasks are queued in Celery for async execution with
    automatic fallback to inline execution if Celery is unavailable.
    
    Task Status Lifecycle:
        pending → queued → running → succeeded (or failed/retrying)
        Stages: queued → started → processing → completed
        Queues: default, high_priority, low_cost (determines execution order)
    
    Attributes:
        id: Primary key (auto-increment)
        workflow_id: Foreign key to Workflow (not nullable, indexed for fast lookup)
        source_task_id: Self-referential foreign key for retry chains (nullable)
            Set when this task is a retry of a previous task.
        name: Task display name or description
        agent: AI agent type (planner, executor, reviewer, etc.)
        stage: Current execution stage (queued/started/processing/completed)
        status: Task outcome (pending/running/succeeded/failed/retrying)
        queue_name: Celery queue assignment (default/high_priority/low_cost)
        input_data: JSON-serialized task inputs (max size varies by queue)
        output_data: JSON-serialized task results (null until completion)
        error_message: Error description if task failed (null on success)
        retries: Number of retry attempts made (0 for first attempt)
        duration_seconds: Task execution time (wall-clock seconds, null if not completed)
        created_at: Task submission timestamp (UTC, indexed for sorting)
        started_at: Execution start timestamp (null if not yet started)
        completed_at: Execution end timestamp (null if still running)
        updated_at: Last status change timestamp (UTC, auto-updated)
    
    Relationships:
        workflow: Back-reference to parent Workflow (many-to-one)
            Inverse: Workflow.tasks
        source_task: Self-referential relationship for retry chains
            Links this task to the task it's retrying (null for first attempt)
    
    Indexes:
        - workflow_id: Fast lookup of workflow's tasks
        - source_task_id: Fast lookup of retry chains
        - status: Quick filtering by outcome
        - created_at: Chronological sorting
        - updated_at: Quick retrieval of recently modified tasks
    
    Example:
        >>> task = Task(
        ...     workflow_id=workflow.id,
        ...     name="Process quarterly report",
        ...     agent="executor",
        ...     status="pending",
        ...     input_data='{"report": "Q1-2026", "format": "markdown"}',
        ...     queue_name="high_priority"
        ... )
        >>> session.add(task)
        >>> session.commit()
        >>> # Later, after execution
        >>> task.status = "succeeded"
        >>> task.output_data = '{"summary": "....", "insights": [...]}'
        >>> task.completed_at = utc_now()
        >>> session.commit()
    """
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
    """Immutable audit trail for compliance, debugging, and forensics.
    
    Records all significant system events (user actions, resource modifications, auth events,
    errors) for compliance auditing, troubleshooting, and security analysis. Audit logs are
    immutable (no updates, only inserts) and indexed by event type and creation time for fast
    query and analysis.
    
    Audit Event Categories:
        - User Actions: login, logout, create_task, delete_workflow, seed_demo_data
        - Resource Changes: workflow_created, task_retried, settings_updated
        - Auth Events: login_failed, permission_denied, token_expired
        - System Events: task_failed, task_timeout, queue_backup_detected
        - Admin Actions: user_deactivated, org_subscription_changed, billing_error
    
    Attributes:
        id: Primary key (auto-increment, audit log identifier)
        actor: User ID or system identifier initiating the action (default: "system")
        event: Event type name (e.g., "workflow_created", "task_retried")
            Used for filtering and reporting on specific event classes
        resource_type: Resource being modified (workflow, task, user, organization)
            Enables quick lookup of all changes to a specific resource type
        resource_id: ID of affected resource (workflow_id, task_id, etc.) or null for system events
        details_json: JSON object with event-specific context (max 10KB per event)
            Examples:
            - workflow_created: {priority: "high", target_model: "gpt-4"}
            - task_retried: {source_task_id: 123, retry_reason: "timeout"}
            - login_failed: {email: "user@...", reason: "invalid_password"}
        created_at: Timestamp when event occurred (UTC, indexed for range queries)
    
    Relationships:
        None (immutable, standalone records)
    
    Indexes:
        - event (indexed): Quick filtering by event type
        - resource_type (indexed): Lookup all changes to a resource type
        - resource_id (indexed): Lookup all changes to a specific resource
        - created_at (indexed): Date-range queries, sorting, pagination
        - (actor, created_at): Composite index for "user's recent actions"
    
    Properties:
        details: Parsed JSON dictionary of event-specific metadata.
            Returns {} on JSON parse error (malformed JSON is gracefully handled).
    
    Example:
        >>> audit = AuditLog(
        ...     actor="user-123",
        ...     event="task_retried",
        ...     resource_type="task",
        ...     resource_id=42,
        ...     details_json='{"source_task_id": 41, "reason": "timeout"}'
        ... )
        >>> session.add(audit)
        >>> session.commit()
        >>> # Query: all workflow creations
        >>> workflow_events = session.query(AuditLog).filter(
        ...     AuditLog.event == "workflow_created"
        ... ).all()
        >>> # Query: all changes to a user
        >>> user_changes = session.query(AuditLog).filter(
        ...     (AuditLog.resource_type == "user") & (AuditLog.resource_id == 123)
        ... ).all()
    """
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
        """Parse details_json string into a Python dictionary.
        
        Returns:
            Parsed JSON as dict. Returns empty {} if JSON is malformed or null.
            Never raises JSONDecodeError (gracefully handles corrupted data).
        
        Example:
            >>> audit = session.query(AuditLog).first()
            >>> audit.details  # {"priority": "high", "model": "gpt-4"}
            >>> audit.details.get("priority", "medium")
            "high"
        """
        try:
            return json.loads(self.details_json or "{}")
        except json.JSONDecodeError:
            return {}


class Organization(Base):
    """Organization with billing and subscription management.
    
    Represents a multi-tenant organization with subscription plans, billing integration,
    and user management. Each organization is isolated from others, with users and usage
    tracked separately. Stripe integration enables self-serve subscription management,
    trial periods, and usage-based billing.
    
    Subscription Plans:
        starter: Free tier, limited usage, trial period only (no payment method required)
        professional: Paid plan, standard usage limits, requires Stripe customer
        enterprise: Custom limits, dedicated support, volume pricing
    
    Subscription Status:
        trialing: In trial period (trial_ends_at is set, no payment method needed)
        active: Paid subscription, current payment method valid
        past_due: Payment failed, grace period active (will downgrade to free after 14 days)
        canceled: User canceled, access revoked
        incomplete: First payment pending (user added payment method but payment not processed)
    
    Attributes:
        id: Primary key (unique organization identifier, typically UUID)
        name: Organization display name
        slug: URL-safe identifier for organization (e.g., "acme-corp", unique)
        email: Organization contact email (unique, indexed)
        stripe_customer_id: Stripe API customer ID for billing (unique, nullable for trial orgs)
        subscription_plan: Current plan tier (starter/professional/enterprise)
        subscription_status: Current payment status (trialing/active/past_due/canceled)
        subscription_item_id: Stripe subscription item ID (for usage-based metering)
        trial_ends_at: Trial expiration time (null if not in trial or trial expired)
        billing_cycle_anchor: Stripe billing cycle start date (monthly anniversary)
        created_at: Organization creation timestamp (UTC, indexed)
        updated_at: Last modification timestamp (UTC, auto-updated)
    
    Relationships:
        users: One-to-Many relationship to User records.
            Cascade: all, delete-orphan
            When organization is deleted, all users are deleted automatically.
        usage_records: One-to-Many relationship to UsageRecord (billing/metering)
            Cascade: all, delete-orphan
            When organization is deleted, all usage records are deleted.
    
    Indexes:
        - name: Fast org lookup by name
        - slug (unique): URL route lookup, fast
        - email (unique): Email-based org lookup
        - stripe_customer_id (unique): Stripe webhook processing
        - subscription_status: Query all orgs in "past_due" status (for dunning)
        - created_at: Chronological sorting, cohort analysis
    
    Example:
        >>> org = Organization(
        ...     id="org-abc123",
        ...     name="Acme Corporation",
        ...     slug="acme-corp",
        ...     email="billing@acme.com",
        ...     subscription_plan="professional",
        ...     subscription_status="active",
        ...     stripe_customer_id="cus_1a2b3c4d5e6f7g"
        ... )
        >>> session.add(org)
        >>> session.commit()
        >>> # Add user to organization
        >>> user = User(id="user-xyz", email="alice@acme.com", org_id=org.id)
        >>> session.add(user)
        >>> session.commit()
    """
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
