"""Tests for Week 3 RBAC (Role-Based Access Control) module.

Tests role permission mapping, permission checking, and role hierarchy logic.
"""

import pytest

from app.rbac import (
    Permission,
    RolePermissionMap,
    WorkspaceRole,
    can_manage_user_role,
    check_permission,
    get_role_hierarchy,
)


class TestWorkspaceRoles:
    """Tests for workspace role enum."""

    def test_workspace_role_values(self) -> None:
        """Test that WorkspaceRole enum has correct values."""
        assert WorkspaceRole.OWNER.value == "owner"
        assert WorkspaceRole.ADMIN.value == "admin"
        assert WorkspaceRole.OPERATOR.value == "operator"
        assert WorkspaceRole.VIEWER.value == "viewer"

    def test_workspace_role_from_string(self) -> None:
        """Test creating WorkspaceRole from string."""
        assert WorkspaceRole("owner") == WorkspaceRole.OWNER
        assert WorkspaceRole("admin") == WorkspaceRole.ADMIN
        assert WorkspaceRole("operator") == WorkspaceRole.OPERATOR
        assert WorkspaceRole("viewer") == WorkspaceRole.VIEWER

    def test_invalid_workspace_role(self) -> None:
        """Test that invalid role raises ValueError."""
        with pytest.raises(ValueError):
            WorkspaceRole("invalid_role")


class TestPermissions:
    """Tests for Permission enum."""

    def test_permission_values(self) -> None:
        """Test that Permission enum has correct values."""
        assert Permission.CREATE_WORKFLOW.value == "create_workflow"
        assert Permission.EXECUTE_TASK.value == "execute_task"
        assert Permission.VIEW_AUDIT.value == "view_audit"
        assert Permission.MANAGE_TEAM.value == "manage_team"
        assert Permission.ADMIN.value == "admin"


class TestRolePermissionMap:
    """Tests for role-to-permission mapping."""

    def test_owner_has_all_permissions(self) -> None:
        """Test that OWNER role has all permissions."""
        permissions = RolePermissionMap.get_permissions("owner")

        expected = {
            Permission.CREATE_WORKFLOW,
            Permission.EXECUTE_TASK,
            Permission.VIEW_AUDIT,
            Permission.MANAGE_TEAM,
            Permission.ADMIN,
        }
        assert permissions == expected

    def test_admin_has_all_permissions(self) -> None:
        """Test that ADMIN role has all permissions."""
        permissions = RolePermissionMap.get_permissions("admin")

        expected = {
            Permission.CREATE_WORKFLOW,
            Permission.EXECUTE_TASK,
            Permission.VIEW_AUDIT,
            Permission.MANAGE_TEAM,
            Permission.ADMIN,
        }
        assert permissions == expected

    def test_operator_has_limited_permissions(self) -> None:
        """Test that OPERATOR role has limited permissions."""
        permissions = RolePermissionMap.get_permissions("operator")

        expected = {
            Permission.CREATE_WORKFLOW,
            Permission.EXECUTE_TASK,
        }
        assert permissions == expected

    def test_viewer_has_no_permissions(self) -> None:
        """Test that VIEWER role has no permissions."""
        permissions = RolePermissionMap.get_permissions("viewer")

        assert permissions == set()

    def test_get_permissions_case_insensitive(self) -> None:
        """Test that get_permissions is case-insensitive."""
        permissions_lower = RolePermissionMap.get_permissions("owner")
        permissions_upper = RolePermissionMap.get_permissions("OWNER")
        permissions_mixed = RolePermissionMap.get_permissions("Owner")

        assert permissions_lower == permissions_upper == permissions_mixed

    def test_get_permissions_unknown_role(self) -> None:
        """Test that unknown role returns empty permissions."""
        permissions = RolePermissionMap.get_permissions("unknown_role")

        assert permissions == set()

    def test_has_permission_owner(self) -> None:
        """Test has_permission for OWNER role."""
        assert RolePermissionMap.has_permission("owner", Permission.CREATE_WORKFLOW)
        assert RolePermissionMap.has_permission("owner", Permission.EXECUTE_TASK)
        assert RolePermissionMap.has_permission("owner", Permission.VIEW_AUDIT)
        assert RolePermissionMap.has_permission("owner", Permission.MANAGE_TEAM)
        assert RolePermissionMap.has_permission("owner", Permission.ADMIN)

    def test_has_permission_admin(self) -> None:
        """Test has_permission for ADMIN role."""
        assert RolePermissionMap.has_permission("admin", Permission.CREATE_WORKFLOW)
        assert RolePermissionMap.has_permission("admin", Permission.EXECUTE_TASK)
        assert RolePermissionMap.has_permission("admin", Permission.MANAGE_TEAM)
        assert RolePermissionMap.has_permission("admin", Permission.ADMIN)

    def test_has_permission_operator(self) -> None:
        """Test has_permission for OPERATOR role."""
        assert RolePermissionMap.has_permission("operator", Permission.CREATE_WORKFLOW)
        assert RolePermissionMap.has_permission("operator", Permission.EXECUTE_TASK)
        assert not RolePermissionMap.has_permission("operator", Permission.MANAGE_TEAM)
        assert not RolePermissionMap.has_permission("operator", Permission.ADMIN)
        assert not RolePermissionMap.has_permission("operator", Permission.VIEW_AUDIT)

    def test_has_permission_viewer(self) -> None:
        """Test has_permission for VIEWER role."""
        assert not RolePermissionMap.has_permission("viewer", Permission.CREATE_WORKFLOW)
        assert not RolePermissionMap.has_permission("viewer", Permission.EXECUTE_TASK)
        assert not RolePermissionMap.has_permission("viewer", Permission.MANAGE_TEAM)
        assert not RolePermissionMap.has_permission("viewer", Permission.ADMIN)

    def test_has_permission_unknown_role(self) -> None:
        """Test has_permission with unknown role."""
        assert not RolePermissionMap.has_permission("unknown", Permission.ADMIN)

    def test_has_permission_case_insensitive(self) -> None:
        """Test that has_permission is case-insensitive."""
        assert RolePermissionMap.has_permission("OWNER", Permission.ADMIN)
        assert RolePermissionMap.has_permission("Owner", Permission.ADMIN)
        assert RolePermissionMap.has_permission("owner", Permission.ADMIN)


class TestCheckPermission:
    """Tests for check_permission utility function."""

    def test_check_permission_granted(self) -> None:
        """Test check_permission when permission is granted."""
        assert check_permission("operator", Permission.EXECUTE_TASK) is True
        assert check_permission("admin", Permission.MANAGE_TEAM) is True
        assert check_permission("owner", Permission.ADMIN) is True

    def test_check_permission_denied(self) -> None:
        """Test check_permission when permission is denied."""
        assert check_permission("operator", Permission.MANAGE_TEAM) is False
        assert check_permission("viewer", Permission.EXECUTE_TASK) is False
        assert check_permission("viewer", Permission.ADMIN) is False

    def test_check_permission_empty_role_raises_error(self) -> None:
        """Test that empty role raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            check_permission("", Permission.ADMIN)

    def test_check_permission_invalid_role(self) -> None:
        """Test check_permission with invalid role."""
        assert check_permission("invalid_role", Permission.ADMIN) is False


class TestRoleHierarchy:
    """Tests for role hierarchy."""

    def test_get_role_hierarchy(self) -> None:
        """Test get_role_hierarchy returns correct levels."""
        hierarchy = get_role_hierarchy()

        assert hierarchy["owner"] == 4
        assert hierarchy["admin"] == 3
        assert hierarchy["operator"] == 2
        assert hierarchy["viewer"] == 1

    def test_role_hierarchy_levels(self) -> None:
        """Test that role hierarchy is correctly ordered."""
        hierarchy = get_role_hierarchy()

        assert hierarchy["owner"] > hierarchy["admin"]
        assert hierarchy["admin"] > hierarchy["operator"]
        assert hierarchy["operator"] > hierarchy["viewer"]

    def test_unknown_role_has_zero_level(self) -> None:
        """Test that unknown role has level 0."""
        hierarchy = get_role_hierarchy()

        assert hierarchy.get("unknown_role", 0) == 0


class TestManageUserRole:
    """Tests for role management (who can assign roles to others)."""

    def test_owner_can_manage_all_roles(self) -> None:
        """Test that OWNER can assign any role to users."""
        assert can_manage_user_role("owner", "admin") is True
        assert can_manage_user_role("owner", "operator") is True
        assert can_manage_user_role("owner", "viewer") is True

    def test_admin_can_manage_lower_roles(self) -> None:
        """Test that ADMIN can assign operator and viewer roles."""
        assert can_manage_user_role("admin", "operator") is True
        assert can_manage_user_role("admin", "viewer") is True

    def test_admin_cannot_manage_owner(self) -> None:
        """Test that ADMIN cannot assign owner role."""
        assert can_manage_user_role("admin", "owner") is False

    def test_admin_cannot_manage_peer_role(self) -> None:
        """Test that ADMIN cannot assign admin role to others."""
        assert can_manage_user_role("admin", "admin") is False

    def test_operator_can_only_manage_viewer(self) -> None:
        """Test that OPERATOR can only assign viewer role."""
        assert can_manage_user_role("operator", "viewer") is True
        assert can_manage_user_role("operator", "operator") is False
        assert can_manage_user_role("operator", "admin") is False
        assert can_manage_user_role("operator", "owner") is False

    def test_viewer_cannot_manage_any_role(self) -> None:
        """Test that VIEWER cannot assign any role."""
        assert can_manage_user_role("viewer", "owner") is False
        assert can_manage_user_role("viewer", "admin") is False
        assert can_manage_user_role("viewer", "operator") is False
        assert can_manage_user_role("viewer", "viewer") is False

    def test_can_manage_user_role_case_insensitive(self) -> None:
        """Test that can_manage_user_role is case-insensitive."""
        assert can_manage_user_role("OWNER", "operator") is True
        assert can_manage_user_role("Owner", "Operator") is True

    def test_unknown_role_cannot_manage(self) -> None:
        """Test that unknown role cannot manage any role."""
        assert can_manage_user_role("unknown_role", "operator") is False
        assert can_manage_user_role("unknown_role", "unknown_role") is False


class TestPermissionScenarios:
    """Tests for realistic permission scenarios."""

    def test_workflow_creation_permissions(self) -> None:
        """Test which roles can create workflows."""
        # Owner, Admin, Operator can create workflows
        assert RolePermissionMap.has_permission("owner", Permission.CREATE_WORKFLOW)
        assert RolePermissionMap.has_permission("admin", Permission.CREATE_WORKFLOW)
        assert RolePermissionMap.has_permission("operator", Permission.CREATE_WORKFLOW)
        # Viewer cannot
        assert not RolePermissionMap.has_permission("viewer", Permission.CREATE_WORKFLOW)

    def test_task_execution_permissions(self) -> None:
        """Test which roles can execute tasks."""
        # Owner, Admin, Operator can execute tasks
        assert RolePermissionMap.has_permission("owner", Permission.EXECUTE_TASK)
        assert RolePermissionMap.has_permission("admin", Permission.EXECUTE_TASK)
        assert RolePermissionMap.has_permission("operator", Permission.EXECUTE_TASK)
        # Viewer cannot
        assert not RolePermissionMap.has_permission("viewer", Permission.EXECUTE_TASK)

    def test_audit_log_viewing_permissions(self) -> None:
        """Test which roles can view audit logs."""
        # Owner, Admin can view audit logs
        assert RolePermissionMap.has_permission("owner", Permission.VIEW_AUDIT)
        assert RolePermissionMap.has_permission("admin", Permission.VIEW_AUDIT)
        # Operator and Viewer cannot
        assert not RolePermissionMap.has_permission("operator", Permission.VIEW_AUDIT)
        assert not RolePermissionMap.has_permission("viewer", Permission.VIEW_AUDIT)

    def test_team_management_permissions(self) -> None:
        """Test which roles can manage team members."""
        # Owner, Admin can manage team
        assert RolePermissionMap.has_permission("owner", Permission.MANAGE_TEAM)
        assert RolePermissionMap.has_permission("admin", Permission.MANAGE_TEAM)
        # Operator, Viewer cannot
        assert not RolePermissionMap.has_permission("operator", Permission.MANAGE_TEAM)
        assert not RolePermissionMap.has_permission("viewer", Permission.MANAGE_TEAM)

    def test_admin_permissions(self) -> None:
        """Test which roles can perform administrative actions."""
        # Owner, Admin can perform admin actions
        assert RolePermissionMap.has_permission("owner", Permission.ADMIN)
        assert RolePermissionMap.has_permission("admin", Permission.ADMIN)
        # Operator, Viewer cannot
        assert not RolePermissionMap.has_permission("operator", Permission.ADMIN)
        assert not RolePermissionMap.has_permission("viewer", Permission.ADMIN)

    def test_operator_capabilities(self) -> None:
        """Test what an operator can do (common case)."""
        # Operators can create workflows and execute tasks
        assert RolePermissionMap.has_permission("operator", Permission.CREATE_WORKFLOW)
        assert RolePermissionMap.has_permission("operator", Permission.EXECUTE_TASK)
        # But cannot manage team, view audit, or perform admin actions
        assert not RolePermissionMap.has_permission("operator", Permission.MANAGE_TEAM)
        assert not RolePermissionMap.has_permission("operator", Permission.VIEW_AUDIT)
        assert not RolePermissionMap.has_permission("operator", Permission.ADMIN)

    def test_viewer_readonly_access(self) -> None:
        """Test that viewers have read-only access (no permissions)."""
        # Viewers cannot do anything that modifies state
        assert not RolePermissionMap.has_permission("viewer", Permission.CREATE_WORKFLOW)
        assert not RolePermissionMap.has_permission("viewer", Permission.EXECUTE_TASK)
        assert not RolePermissionMap.has_permission("viewer", Permission.MANAGE_TEAM)
        assert not RolePermissionMap.has_permission("viewer", Permission.VIEW_AUDIT)
        assert not RolePermissionMap.has_permission("viewer", Permission.ADMIN)


class TestPermissionEdgeCases:
    """Tests for edge cases in permission checking."""

    def test_permissions_are_immutable(self) -> None:
        """Test that modifying returned permission set doesn't affect role."""
        permissions = RolePermissionMap.get_permissions("operator")
        original_count = len(permissions)

        # Try to modify the returned set
        permissions.add(Permission.ADMIN)

        # Original role should not be affected
        permissions_again = RolePermissionMap.get_permissions("operator")
        assert len(permissions_again) == original_count
        assert Permission.ADMIN not in permissions_again

    def test_whitespace_in_role_name(self) -> None:
        """Test that role names with whitespace are handled."""
        # Empty role (edge case)
        permissions = RolePermissionMap.get_permissions("  ")
        assert permissions == set()

    def test_special_characters_in_role_name(self) -> None:
        """Test that role names with special characters return empty permissions."""
        permissions = RolePermissionMap.get_permissions("owner@#$%")
        assert permissions == set()

    def test_none_role_handling(self) -> None:
        """Test graceful handling of None role (edge case)."""
        # This should raise an AttributeError or ValueError due to .lower()
        try:
            RolePermissionMap.get_permissions(None)
        except (AttributeError, TypeError):
            pass  # Expected

    def test_numeric_role_handling(self) -> None:
        """Test handling of numeric role (edge case)."""
        permissions = RolePermissionMap.get_permissions("123")
        assert permissions == set()
