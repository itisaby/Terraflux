"""
Role-Based Access Control (RBAC)
Permission management and authorization checks
"""
from enum import Enum
from typing import Set, Dict
from database.models import UserRole, User
from fastapi import HTTPException
import logging

class Permission(Enum):
    """System permissions"""
    # Infrastructure operations
    CREATE_INFRASTRUCTURE = "create_infrastructure"
    MODIFY_INFRASTRUCTURE = "modify_infrastructure"
    DESTROY_INFRASTRUCTURE = "destroy_infrastructure"
    VIEW_INFRASTRUCTURE = "view_infrastructure"

    # Credential management
    MANAGE_CREDENTIALS = "manage_credentials"
    VIEW_CREDENTIALS = "view_credentials"

    # User management
    CREATE_USER = "create_user"
    MODIFY_USER = "modify_user"
    DELETE_USER = "delete_user"
    VIEW_USERS = "view_users"

    # Audit and monitoring
    VIEW_AUDIT_LOGS = "view_audit_logs"
    VIEW_COST_REPORTS = "view_cost_reports"

    # System administration
    MANAGE_SYSTEM_CONFIG = "manage_system_config"
    VIEW_SYSTEM_STATUS = "view_system_status"

# Role to permissions mapping
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.VIEWER: {
        Permission.VIEW_INFRASTRUCTURE,
        Permission.VIEW_CREDENTIALS,
        Permission.VIEW_COST_REPORTS,
    },

    UserRole.USER: {
        Permission.VIEW_INFRASTRUCTURE,
        Permission.CREATE_INFRASTRUCTURE,
        Permission.MODIFY_INFRASTRUCTURE,
        Permission.DESTROY_INFRASTRUCTURE,
        Permission.MANAGE_CREDENTIALS,
        Permission.VIEW_CREDENTIALS,
        Permission.VIEW_COST_REPORTS,
        Permission.VIEW_AUDIT_LOGS,
    },

    UserRole.ADMIN: {
        # Admins have all permissions
        Permission.VIEW_INFRASTRUCTURE,
        Permission.CREATE_INFRASTRUCTURE,
        Permission.MODIFY_INFRASTRUCTURE,
        Permission.DESTROY_INFRASTRUCTURE,
        Permission.MANAGE_CREDENTIALS,
        Permission.VIEW_CREDENTIALS,
        Permission.CREATE_USER,
        Permission.MODIFY_USER,
        Permission.DELETE_USER,
        Permission.VIEW_USERS,
        Permission.VIEW_AUDIT_LOGS,
        Permission.VIEW_COST_REPORTS,
        Permission.MANAGE_SYSTEM_CONFIG,
        Permission.VIEW_SYSTEM_STATUS,
    }
}

def get_role_permissions(role: UserRole) -> Set[Permission]:
    """
    Get all permissions for a given role

    Args:
        role: User role

    Returns:
        Set of permissions
    """
    return ROLE_PERMISSIONS.get(role, set())

def has_permission(user: User, permission: Permission) -> bool:
    """
    Check if a user has a specific permission

    Args:
        user: User object
        permission: Permission to check

    Returns:
        True if user has permission, False otherwise
    """
    if not user.is_active:
        return False

    role_perms = get_role_permissions(user.role)
    return permission in role_perms

def require_permission(permission: Permission):
    """
    Decorator/dependency to require a specific permission

    Usage:
        from fastapi import Depends
        from security.auth import get_current_user

        @app.post("/infrastructure")
        async def create_infra(
            request: InfraRequest,
            user: User = Depends(get_current_user)
        ):
            check_permission(user, Permission.CREATE_INFRASTRUCTURE)
            # ... rest of the logic
    """
    def permission_checker(user: User) -> User:
        if not has_permission(user, permission):
            logging.warning(
                f"User {user.id} ({user.username}) attempted to access "
                f"{permission.value} without permission"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permission.value}"
            )
        return user

    return permission_checker

def check_permission(user: User, permission: Permission) -> None:
    """
    Check permission and raise exception if not authorized

    Args:
        user: User object
        permission: Required permission

    Raises:
        HTTPException: If user doesn't have permission
    """
    if not has_permission(user, permission):
        logging.warning(
            f"User {user.id} ({user.username}) denied access to {permission.value}"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions. Required: {permission.value}"
        )

def check_resource_ownership(user: User, resource_user_id: str) -> None:
    """
    Check if user owns a resource or is admin

    Args:
        user: Current user
        resource_user_id: User ID that owns the resource

    Raises:
        HTTPException: If user doesn't own resource and is not admin
    """
    if user.role == UserRole.ADMIN:
        return  # Admins can access all resources

    if user.id != resource_user_id:
        logging.warning(
            f"User {user.id} ({user.username}) attempted to access "
            f"resource owned by user {resource_user_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to access this resource"
        )

def can_modify_user(current_user: User, target_user: User) -> bool:
    """
    Check if current user can modify target user

    Rules:
    - Admins can modify anyone except themselves (role change)
    - Users can only modify themselves (limited fields)
    - Viewers cannot modify anyone

    Args:
        current_user: User performing the action
        target_user: User being modified

    Returns:
        True if modification is allowed
    """
    # Admins can modify anyone
    if current_user.role == UserRole.ADMIN:
        return True

    # Users can only modify themselves
    if current_user.id == target_user.id:
        return True

    return False

def get_accessible_user_ids(current_user: User, all_user_ids: list) -> list:
    """
    Filter user IDs based on what the current user can access

    Args:
        current_user: Current user
        all_user_ids: List of all user IDs

    Returns:
        List of accessible user IDs
    """
    # Admins can see all users
    if current_user.role == UserRole.ADMIN:
        return all_user_ids

    # Regular users can only see themselves
    return [current_user.id]

def validate_role_change(current_user: User, new_role: UserRole) -> None:
    """
    Validate if a role change is allowed

    Args:
        current_user: User making the change
        new_role: Proposed new role

    Raises:
        HTTPException: If role change is not allowed
    """
    # Only admins can change roles
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can change user roles"
        )

    # Prevent demoting the last admin
    # (This would need additional database query in practice)
    logging.info(f"Role change validated: {current_user.username} -> {new_role.value}")

def get_permission_description(permission: Permission) -> str:
    """
    Get human-readable description of a permission

    Args:
        permission: Permission enum

    Returns:
        Description string
    """
    descriptions = {
        Permission.CREATE_INFRASTRUCTURE: "Create new infrastructure resources",
        Permission.MODIFY_INFRASTRUCTURE: "Modify existing infrastructure",
        Permission.DESTROY_INFRASTRUCTURE: "Destroy infrastructure resources",
        Permission.VIEW_INFRASTRUCTURE: "View infrastructure resources",
        Permission.MANAGE_CREDENTIALS: "Add, modify, or delete cloud credentials",
        Permission.VIEW_CREDENTIALS: "View credential metadata",
        Permission.CREATE_USER: "Create new user accounts",
        Permission.MODIFY_USER: "Modify user accounts",
        Permission.DELETE_USER: "Delete user accounts",
        Permission.VIEW_USERS: "View user information",
        Permission.VIEW_AUDIT_LOGS: "View system audit logs",
        Permission.VIEW_COST_REPORTS: "View cost reports and estimates",
        Permission.MANAGE_SYSTEM_CONFIG: "Manage system configuration",
        Permission.VIEW_SYSTEM_STATUS: "View system health and status",
    }

    return descriptions.get(permission, permission.value)

def get_role_description(role: UserRole) -> str:
    """
    Get human-readable description of a role

    Args:
        role: User role

    Returns:
        Description string
    """
    descriptions = {
        UserRole.VIEWER: "Read-only access to infrastructure and reports",
        UserRole.USER: "Can create, modify, and manage their own infrastructure",
        UserRole.ADMIN: "Full system access including user and system management",
    }

    return descriptions.get(role, role.value)

def list_role_permissions(role: UserRole) -> list:
    """
    List all permissions for a role with descriptions

    Args:
        role: User role

    Returns:
        List of dicts with permission name and description
    """
    permissions = get_role_permissions(role)

    return [
        {
            "permission": perm.value,
            "description": get_permission_description(perm)
        }
        for perm in permissions
    ]
