"""
Audit Logging Utilities
Provides comprehensive audit logging for security-sensitive operations
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import Request
from database.models import AuditLog
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


def redact_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact sensitive fields from audit logs

    Args:
        data: Dictionary that may contain sensitive data

    Returns:
        Dictionary with sensitive fields redacted
    """
    if not isinstance(data, dict):
        return data

    sensitive_keys = [
        'password', 'token', 'secret', 'key', 'credential',
        'access_key', 'secret_key', 'api_key', 'private_key',
        'authorization', 'auth', 'session'
    ]

    redacted = {}
    for key, value in data.items():
        # Check if key contains sensitive terms
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value

    return redacted


async def create_audit_log(
    db: Session,
    user_id: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    request_data: Optional[Dict[str, Any]] = None,
    response_data: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    request: Optional[Request] = None
):
    """
    Create comprehensive audit log entry

    Args:
        db: Database session
        user_id: User ID performing the action
        action: Action being performed (e.g., "login", "create_resource")
        resource_type: Type of resource being acted upon
        resource_id: ID of the specific resource
        request_data: Request data (will be redacted)
        response_data: Response data (will be redacted)
        success: Whether the action was successful
        error_message: Error message if action failed
        request: FastAPI Request object to extract IP and user agent
    """
    try:
        # Extract client information
        client_ip = "unknown"
        user_agent = "unknown"

        if request:
            if request.client:
                client_ip = request.client.host
            user_agent = request.headers.get("user-agent", "unknown")

        # Redact sensitive data
        sanitized_request = redact_sensitive_data(request_data) if request_data else None
        sanitized_response = redact_sensitive_data(response_data) if response_data else None

        # Create audit log entry
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_data=json.dumps(sanitized_request) if sanitized_request else None,
            response_data=json.dumps(sanitized_response) if sanitized_response else None,
            success=success,
            error_message=error_message,
            ip_address=client_ip,
            user_agent=user_agent,
            timestamp=datetime.utcnow()
        )

        db.add(audit_log)
        db.commit()

        # Log to application logs for external SIEM integration
        log_message = f"AUDIT: {action} by user {user_id} from {client_ip} - {'SUCCESS' if success else 'FAILED'}"
        if success:
            logger.info(log_message)
        else:
            logger.warning(f"{log_message} - {error_message}")

    except Exception as e:
        logger.exception("Failed to create audit log")
        # Don't fail the main operation if audit logging fails
        db.rollback()


class AuditLogger:
    """
    Context manager for audit logging
    Automatically logs success/failure of operations
    """

    def __init__(
        self,
        db: Session,
        user_id: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        request: Optional[Request] = None
    ):
        self.db = db
        self.user_id = user_id
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.request = request
        self.success = False
        self.error_message = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.success = True
        else:
            self.error_message = str(exc_val)

        await create_audit_log(
            db=self.db,
            user_id=self.user_id,
            action=self.action,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            success=self.success,
            error_message=self.error_message,
            request=self.request
        )

        # Don't suppress exceptions
        return False
