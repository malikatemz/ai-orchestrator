"""Role-based access control (RBAC) and permission checking"""

from typing import Dict, List, Set
from enum import Enum

from ..models import UserRole


# ============ Permission Matrix ============

class Permission(str, Enum):
    """All available permissions"""
    # User management
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    
    # Workflow/Task operations
    RUN_WORKFLOWS = "run_workflows"
    CREATE_WORKFLOWS = "create_workflows"
    DELETE_WORKFLOWS = "delete_workflows"
    
    # Viewing/Logging
    VIEW_LOGS = "view_logs"
    VIEW_OWN_LOGS = "view_own_logs"
    
    # Billing
    VIEW_BILLING = "view_billing"
    MANAGE_SUBSCRIPTION = "manage_subscription"
    VIEW_AUDIT = "view_audit"
    
    # Admin
    ADMIN_PANEL = "admin_panel"
    VIEW_METRICS = "view_metrics"


ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.OWNER: {
        # Owners have all permissions
        Permission.MANAGE_USERS,
        Permission.MANAGE_ROLES,
        Permission.RUN_WORKFLOWS,
        Permission.CREATE_WORKFLOWS,
        Permission.DELETE_WORKFLOWS,
        Permission.VIEW_LOGS,
        Permission.VIEW_OWN_LOGS,
        Permission.VIEW_BILLING,
        Permission.MANAGE_SUBSCRIPTION,
        Permission.VIEW_AUDIT,
        Permission.ADMIN_PANEL,
        Permission.VIEW_METRICS,
    },
    
    UserRole.ADMIN: {
        # Admins can manage operations but not billing
        Permission.MANAGE_USERS,
        Permission.RUN_WORKFLOWS,
        Permission.CREATE_WORKFLOWS,
        Permission.DELETE_WORKFLOWS,
        Permission.VIEW_LOGS,
        Permission.VIEW_AUDIT,
        Permission.VIEW_METRICS,
    },
    
    UserRole.MEMBER: {
        # Members can run workflows and view their own logs
        Permission.RUN_WORKFLOWS,
        Permission.CREATE_WORKFLOWS,
        Permission.VIEW_OWN_LOGS,
        Permission.VIEW_METRICS,
    },
    
    UserRole.VIEWER: {
        # Viewers are read-only
        Permission.VIEW_LOGS,
        Permission.VIEW_OWN_LOGS,
    },
    
    UserRole.BILLING_ADMIN: {
        # Billing admins manage subscriptions
        Permission.VIEW_BILLING,
        Permission.MANAGE_SUBSCRIPTION,
        Permission.VIEW_AUDIT,
    },
}


# ============ Permission Checking ============

def get_user_permissions(role: UserRole) -> Set[Permission]:
    """Get all permissions for a role"""
    return ROLE_PERMISSIONS.get(role, set())


def check_permission(role: UserRole, required_permission: Permission) -> bool:
    """Check if role has a specific permission"""
    return required_permission in get_user_permissions(role)


def require_permission(role: UserRole, required_permission: Permission) -> None:
    """
    Enforce permission - raise PermissionError if denied.
    
    Usage in FastAPI dependency:
      @router.get("/admin")
      async def admin_panel(current_user = Depends(get_current_user)):
          require_permission(current_user.role, Permission.ADMIN_PANEL)
          ...
    """
    if not check_permission(role, required_permission):
        raise PermissionError(
            f"User lacks required permission: {required_permission.value}"
        )


def require_any_permission(role: UserRole, permissions: List[Permission]) -> None:
    """Check if role has any of the given permissions"""
    for perm in permissions:
        if check_permission(role, perm):
            return
    
    perm_names = ", ".join([p.value for p in permissions])
    raise PermissionError(f"User lacks all of required permissions: {perm_names}")


def require_all_permissions(role: UserRole, permissions: List[Permission]) -> None:
    """Check if role has all given permissions"""
    for perm in permissions:
        if not check_permission(role, perm):
            raise PermissionError(f"User lacks required permission: {perm.value}")
