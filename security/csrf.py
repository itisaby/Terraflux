"""
CSRF Protection
Simple CSRF token generation and validation for state-changing operations
"""
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import HTTPException, Header
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

# Get secret key from environment
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY must be set for CSRF protection")

# Initialize serializer
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="csrf-protection")

# Token expiration time (in seconds)
CSRF_TOKEN_EXPIRATION = 3600  # 1 hour


def generate_csrf_token(user_id: str) -> str:
    """
    Generate a CSRF token for a user

    Args:
        user_id: User ID to tie token to

    Returns:
        Signed CSRF token
    """
    return serializer.dumps(user_id)


def validate_csrf_token(token: str, user_id: str, max_age: int = CSRF_TOKEN_EXPIRATION) -> bool:
    """
    Validate a CSRF token

    Args:
        token: CSRF token to validate
        user_id: Expected user ID
        max_age: Maximum age of token in seconds

    Returns:
        True if valid, False otherwise
    """
    try:
        token_user_id = serializer.loads(token, max_age=max_age)
        return token_user_id == user_id
    except (BadSignature, SignatureExpired) as e:
        logger.warning(f"CSRF token validation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"CSRF token validation error: {e}")
        return False


async def verify_csrf_token(
    x_csrf_token: Optional[str] = Header(None),
    user_id: Optional[str] = None
):
    """
    FastAPI dependency to verify CSRF token

    Args:
        x_csrf_token: CSRF token from X-CSRF-Token header
        user_id: User ID to validate against

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not x_csrf_token:
        raise HTTPException(
            status_code=403,
            detail="CSRF token missing. Include X-CSRF-Token header."
        )

    if not user_id:
        raise HTTPException(
            status_code=403,
            detail="User context required for CSRF validation"
        )

    if not validate_csrf_token(x_csrf_token, user_id):
        raise HTTPException(
            status_code=403,
            detail="Invalid or expired CSRF token"
        )


class CSRFProtect:
    """
    Simple CSRF protection class for FastAPI
    """

    @staticmethod
    def generate_token(user_id: str) -> str:
        """Generate CSRF token"""
        return generate_csrf_token(user_id)

    @staticmethod
    async def validate(token: Optional[str], user_id: str):
        """Validate CSRF token"""
        await verify_csrf_token(x_csrf_token=token, user_id=user_id)
