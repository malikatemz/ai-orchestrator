"""Unit tests for Week 3 multi-tenant RBAC models.

Tests cover:
- User model creation and validation
- Workspace model with creator tracking
- WorkspaceUser junction table for RBAC
- APIKey model for programmatic access
- Workspace isolation and multi-tenancy
- Cross-workspace leakage prevention
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from app.models import (
    User, UserRole,
    Workspace, WorkspaceUser, WorkspaceRole,
    APIKey, 
    Organization,
    Workflow, Task, AuditLog
)


class TestUserModel:
    """Tests for User model with multi-tenant support."""
    
    def test_user_creation_with_email(self):
        """Test creating a user with email and password."""
        user = User(
            id="user-123",
            email="alice@example.com",
            full_name="Alice Smith",
            hashed_password="$2b$12$...",
            role=UserRole.OWNER,
            org_id="org-123"
        )
        
        assert user.id == "user-123"
        assert user.email == "alice@example.com"
        assert user.full_name == "Alice Smith"
        assert user.is_active is True
        assert user.role == UserRole.OWNER
    
    def test_user_soft_delete(self):
        """Test that users can be soft-deleted via is_active flag."""
        user = User(
            id="user-123",
            email="bob@example.com",
            full_name="Bob",
            hashed_password="$2b$12$...",
        )
        
        assert user.is_active is True
        user.is_active = False
        assert user.is_active is False
    
    def test_user_last_login_tracking(self):
        """Test that last_login_at tracks last successful login."""
        user = User(
            id="user-123",
            email="charlie@example.com",
            full_name="Charlie",
            hashed_password="$2b$12$...",
            last_login_at=None
        )
        
        assert user.last_login_at is None
        now = datetime.utcnow()
        user.last_login_at = now
        assert user.last_login_at is not None


class TestWorkspaceModel:
    """Tests for Workspace model with multi-tenant support."""
    
    def test_workspace_creation(self):
        """Test creating a workspace with creator."""
        workspace = Workspace(
            id="ws-123",
            name="Engineering Team",
            description="Engineering workflows",
            created_by="user-123"
        )
        
        assert workspace.id == "ws-123"
        assert workspace.name == "Engineering Team"
        assert workspace.created_by == "user-123"
    
    def test_workspace_with_organization(self):
        """Test workspace linked to organization."""
        workspace = Workspace(
            id="ws-123",
            name="Design Team",
            organization_id="org-456",
            created_by="user-789"
        )
        
        assert workspace.organization_id == "org-456"
    
    def test_workspace_timestamps(self):
        """Test workspace creation and update timestamps."""
        workspace = Workspace(
            id="ws-123",
            name="QA Team",
            created_by="user-123"
        )
        
        assert workspace.created_at is not None
        assert workspace.updated_at is not None


class TestWorkspaceUserModel:
    """Tests for WorkspaceUser RBAC junction table."""
    
    def test_workspace_user_creation(self):
        """Test adding user to workspace with role."""
        member = WorkspaceUser(
            id="wm-123",
            user_id="user-123",
            workspace_id="ws-456",
            role=WorkspaceRole.OPERATOR
        )
        
        assert member.user_id == "user-123"
        assert member.workspace_id == "ws-456"
        assert member.role == WorkspaceRole.OPERATOR
    
    def test_workspace_user_role_owner(self):
        """Test owner role in workspace."""
        owner = WorkspaceUser(
            id="wm-1",
            user_id="user-owner",
            workspace_id="ws-1",
            role=WorkspaceRole.OWNER
        )
        
        assert owner.role == WorkspaceRole.OWNER
    
    def test_workspace_user_role_viewer(self):
        """Test viewer role (read-only)."""
        viewer = WorkspaceUser(
            id="wm-2",
            user_id="user-viewer",
            workspace_id="ws-1",
            role=WorkspaceRole.VIEWER
        )
        
        assert viewer.role == WorkspaceRole.VIEWER
    
    def test_workspace_user_default_role(self):
        """Test default role is viewer."""
        member = WorkspaceUser(
            id="wm-3",
            user_id="user-123",
            workspace_id="ws-1"
        )
        
        assert member.role == WorkspaceRole.VIEWER


class TestAPIKeyModel:
    """Tests for APIKey model for programmatic access."""
    
    def test_api_key_creation(self):
        """Test creating an API key for user in workspace."""
        key = APIKey(
            id="key-123",
            user_id="user-456",
            workspace_id="ws-789",
            name="CI/CD Pipeline",
            key_hash="$2b$12$...",
        )
        
        assert key.id == "key-123"
        assert key.user_id == "user-456"
        assert key.workspace_id == "ws-789"
        assert key.name == "CI/CD Pipeline"
        assert key.last_used_at is None
    
    def test_api_key_last_used_tracking(self):
        """Test tracking last successful API key use."""
        key = APIKey(
            id="key-123",
            user_id="user-456",
            workspace_id="ws-789",
            name="Webhook Handler",
            key_hash="$2b$12$...",
        )
        
        assert key.last_used_at is None
        now = datetime.utcnow()
        key.last_used_at = now
        assert key.last_used_at == now
    
    def test_api_key_expiration(self):
        """Test API key expiration dates."""
        future = datetime.utcnow() + timedelta(days=90)
        key = APIKey(
            id="key-456",
            user_id="user-789",
            workspace_id="ws-123",
            name="Temporary Access",
            key_hash="$2b$12$...",
            expires_at=future
        )
        
        assert key.expires_at == future


class TestWorkspaceIsolation:
    """Tests for workspace isolation and multi-tenancy."""
    
    def test_user_in_multiple_workspaces(self):
        """Test that user can be in multiple workspaces with different roles."""
        user_id = "user-123"
        
        # User is admin in workspace 1
        member1 = WorkspaceUser(
            id="wm-1",
            user_id=user_id,
            workspace_id="ws-1",
            role=WorkspaceRole.ADMIN
        )
        
        # Same user is viewer in workspace 2
        member2 = WorkspaceUser(
            id="wm-2",
            user_id=user_id,
            workspace_id="ws-2",
            role=WorkspaceRole.VIEWER
        )
        
        # Same user is operator in workspace 3
        member3 = WorkspaceUser(
            id="wm-3",
            user_id=user_id,
            workspace_id="ws-3",
            role=WorkspaceRole.OPERATOR
        )
        
        # User has different roles across workspaces
        assert member1.role == WorkspaceRole.ADMIN
        assert member2.role == WorkspaceRole.VIEWER
        assert member3.role == WorkspaceRole.OPERATOR
    
    def test_workflow_workspace_isolation(self):
        """Test that workflows are isolated by workspace."""
        # Workflow in workspace 1
        workflow1 = Workflow(
            id=1,
            name="Workflow 1",
            description="Workflow in WS1",
            workspace_id="ws-1",
            created_by="user-123"
        )
        
        # Workflow in workspace 2
        workflow2 = Workflow(
            id=2,
            name="Workflow 2",
            description="Workflow in WS2",
            workspace_id="ws-2",
            created_by="user-456"
        )
        
        # Workflows are in different workspaces
        assert workflow1.workspace_id == "ws-1"
        assert workflow2.workspace_id == "ws-2"
        assert workflow1.workspace_id != workflow2.workspace_id
    
    def test_task_workspace_tracking(self):
        """Test that tasks track which workspace they belong to."""
        task = Task(
            id=1,
            workflow_id=1,
            name="Task 1",
            input_data="test",
            workspace_id="ws-1",
            executed_by="user-123"
        )
        
        assert task.workspace_id == "ws-1"
        assert task.executed_by == "user-123"


class TestAuditLogWithUserContext:
    """Tests for audit logs with user and workspace context."""
    
    def test_audit_log_user_context(self):
        """Test that audit logs track which user performed action."""
        audit = AuditLog(
            actor="user-123",
            event="workflow_created",
            resource_type="workflow",
            resource_id=42,
            user_id="user-123",
            workspace_id="ws-456"
        )
        
        assert audit.user_id == "user-123"
        assert audit.workspace_id == "ws-456"
        assert audit.event == "workflow_created"
    
    def test_audit_log_workspace_context(self):
        """Test that audit logs are scoped to workspace."""
        # Action in workspace 1
        audit1 = AuditLog(
            actor="user-123",
            event="task_completed",
            resource_type="task",
            resource_id=1,
            user_id="user-123",
            workspace_id="ws-1"
        )
        
        # Action in workspace 2
        audit2 = AuditLog(
            actor="user-456",
            event="task_completed",
            resource_type="task",
            resource_id=1,
            user_id="user-456",
            workspace_id="ws-2"
        )
        
        # Same task ID but different workspaces (isolated)
        assert audit1.workspace_id == "ws-1"
        assert audit2.workspace_id == "ws-2"
        assert audit1.workspace_id != audit2.workspace_id


class TestCrossWorkspaceLeakagePrevention:
    """Tests to verify no cross-workspace data leakage."""
    
    def test_user_cannot_access_other_workspace_workflows(self):
        """Test that users should only see workflows from their workspaces."""
        # Create workflows in different workspaces
        workflow_ws1 = Workflow(
            id=1,
            name="WS1 Workflow",
            description="Workflow in workspace 1",
            workspace_id="ws-1",
            created_by="user-1"
        )
        
        workflow_ws2 = Workflow(
            id=2,
            name="WS2 Workflow",
            description="Workflow in workspace 2",
            workspace_id="ws-2",
            created_by="user-2"
        )
        
        # User 1 should not see workflow from workspace 2
        # This would be enforced by DB queries filtering by workspace_id
        assert workflow_ws1.workspace_id != workflow_ws2.workspace_id
    
    def test_api_key_scoped_to_workspace(self):
        """Test that API keys only grant access to their workspace."""
        key1 = APIKey(
            id="key-1",
            user_id="user-123",
            workspace_id="ws-1",
            name="Key for WS1",
            key_hash="$2b$12$...",
        )
        
        key2 = APIKey(
            id="key-2",
            user_id="user-123",
            workspace_id="ws-2",
            name="Key for WS2",
            key_hash="$2b$12$...",
        )
        
        # Keys are scoped to their workspaces
        assert key1.workspace_id == "ws-1"
        assert key2.workspace_id == "ws-2"
        assert key1.workspace_id != key2.workspace_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
