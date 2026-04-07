"""Role-Based Access Control (RBAC) and permission management.

This module defines workspace roles, permissions, and permission checking logic.
Roles are hierarchical: OWNER > ADMIN > OPERATOR > VIEWER.
"""

from enum import Enum
from typing import Optional, Set

from .observability import configure_logging

logger = configure_logging()


class Permission(str, Enum):
    """Permissions for workspace operations.

    Attributes:
        CREATE_WORKFLOW: Create new workflows
        EXECUTE_TASK: Execute (run) tasks
        VIEW_AUDIT: View audit logs
        MANAGE_TEAM: Invite/remove users, change roles
        ADMIN: All administrative operations (delete, settings, etc.)
    """

    CREATE_WORKFLOW = "create_workflow"
    EXECUTE_TASK = "execute_task"
    VIEW_AUDIT = "view_audit"
    MANAGE_TEAM = "manage_team"
    ADMIN = "admin"


class WorkspaceRole(str, Enum):
    """Workspace-level roles with hierarchical permissions.

    Attributes:
        OWNER: Full control (all permissions)
        ADMIN: Administrative access (all except full deletion)
        OPERATOR: Can execute tasks and manage workflows (no user management)
        VIEWER: Read-only access (view workflows and audit logs only)
    """

    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class RolePermissionMap:
    """Maps roles to their associated permissions.

    Implements hierarchical RBAC where higher roles include lower role permissions.
    OWNER > ADMIN > OPERATOR > VIEWER (left to right in permission hierarchy).
    """

    # Define permission set for each role
    _ROLE_PERMISSIONS: dict[WorkspaceRole, Set[Permission]] = {
        WorkspaceRole.OWNER: {
            Permission.CREATE_WORKFLOW,
            Permission.EXECUTE_TASK,
            Permission.VIEW_AUDIT,
            Permission.MANAGE_TEAM,
            Permission.ADMIN,
        },
        WorkspaceRole.ADMIN: {
            Permission.CREATE_WORKFLOW,
            Permission.EXECUTE_TASK,
            Permission.VIEW_AUDIT,
            Permission.MANAGE_TEAM,
            Permission.ADMIN,
        },
        WorkspaceRole.OPERATOR: {
            Permission.CREATE_WORKFLOW,
            Permission.EXECUTE_TASK,
        },
        WorkspaceRole.VIEWER: set(),  # No permissions
    }

    @classmethod
    def get_permissions(cls, role: str) -> Set[Permission]:
        """Get all permissions for a role.

        Args:
            role: Role name (owner, admin, operator, viewer)

        Returns:
            Set of Permission enums for the role

        Example:
            >>> RolePermissionMap.get_permissions("operator")
            {<Permission.CREATE_WORKFLOW: 'create_workflow'>, ...}
        """
        try:
            workspace_role = WorkspaceRole(role.lower())
            return cls._ROLE_PERMISSIONS.get(workspace_role, set()).copy()
        except ValueError:
            # Unknown role, return empty permissions
            logger.warning(f"Unknown role: {role}")
            return set()

    @classmethod
    def has_permission(
        cls, role: str, required_permission: Permission
    ) -> bool:
        """Check if role has a specific permission.

        Args:
            role: Role name (owner, admin, operator, viewer)
            required_permission: Permission to check

        Returns:
            True if role has permission, False otherwise

        Example:
            >>> RolePermissionMap.has_permission("operator", Permission.EXECUTE_TASK)
            True
            >>> RolePermissionMap.has_permission("viewer", Permission.ADMIN)
            False
        """
        permissions = cls.get_permissions(role)
        return required_permission in permissions


def check_permission(user_workspace_role: str, required_permission: Permission) -> bool:
    """Check if user's workspace role has required permission.

    Utility function for use in endpoints and middleware.

    Args:
        user_workspace_role: User's role in workspace (e.g., "operator")
        required_permission: Required permission to perform action

    Returns:
        True if user has permission, False otherwise

    Raises:
        ValueError: If user_workspace_role or required_permission is invalid

    Example:
        >>> if check_permission("operator", Permission.EXECUTE_TASK):
        ...     # Execute task
        ... else:
        ...     # Return 403 Forbidden
    """
    if not user_workspace_role:
        raise ValueError("user_workspace_role cannot be empty")

    return RolePermissionMap.has_permission(user_workspace_role, required_permission)


def get_role_hierarchy() -> dict[str, int]:
    """Get role hierarchy levels (higher = more permissions).

    Used for permission checks and role comparisons.

    Returns:
        Dictionary mapping role names to hierarchy levels

    Example:
        >>> hierarchy = get_role_hierarchy()
        >>> hierarchy["owner"] > hierarchy["operator"]
        True
    """
    return {
        "owner": 4,
        "admin": 3,
        "operator": 2,
        "viewer": 1,
    }


def can_manage_user_role(manager_role: str, target_role: str) -> bool:
    """Check if manager can change a user's role (hierarchy-based).

    A user can only manage roles at or below their own level.
    For example, operators cannot manage other operators (equality not allowed).

    Args:
        manager_role: Role of user trying to change another user's role
        target_role: Role being assigned to target user

    Returns:
        True if manager can assign target_role to another user

    Example:
        >>> can_manage_user_role("admin", "operator")  # Admin can set operator
        True
        >>> can_manage_user_role("operator", "admin")  # Operator can't set admin
        False
        >>> can_manage_user_role("operator", "operator")  # Operator can't manage peer
        False
    """
    hierarchy = get_role_hierarchy()
    manager_level = hierarchy.get(manager_role.lower(), 0)
    target_level = hierarchy.get(target_role.lower(), 0)

    # Manager must be strictly higher level than target
    return manager_level > target_level
