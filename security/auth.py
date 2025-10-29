"""
Authentication and Authorization
JWT-based authentication with password hashing
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import os
import logging

from database.models import User, UserRole
from database.session import get_db

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "your-secret-key-change-in-production":
    raise ValueError(
        "SECRET_KEY environment variable must be set with a secure random value. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Precomputed dummy hash for timing protection (constant-time verification)
# This is hashed once at startup to avoid timing differences in authentication
DUMMY_PASSWORD_HASH = pwd_context.hash("dummy_password_to_maintain_constant_timing")

# HTTP Bearer token
security = HTTPBearer()

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Data to encode in the token (e.g., {"sub": user_id})
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token

    Args:
        token: JWT token to decode

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logging.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password
    Uses constant-time comparison to prevent timing attacks

    Args:
        db: Database session
        username: Username
        password: Plain text password

    Returns:
        User object if authentication successful, None otherwise
    """
    user = db.query(User).filter(User.username == username).first()

    # Always verify password even if user doesn't exist
    # This prevents timing attacks for username enumeration
    if not user:
        # Perform dummy verification to maintain constant timing
        pwd_context.verify("dummy_password_to_maintain_constant_timing", DUMMY_PASSWORD_HASH)
        logging.warning(f"Failed login attempt for non-existent user: {username}")
        return None

    # Check if user is active
    if not user.is_active:
        # Still verify password to maintain constant timing
        verify_password(password, user.password_hash)
        logging.warning(f"Failed login attempt for inactive user: {username}")
        return None

    # Verify password
    if not verify_password(password, user.password_hash):
        logging.warning(f"Failed login attempt with wrong password for user: {username}")
        return None

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    logging.info(f"Successful login for user: {username}")
    return user

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user

    Usage:
        @app.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            return {"user_id": current_user.id}

    Args:
        credentials: HTTP Authorization Bearer token
        db: Database session

    Returns:
        Current user

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")

    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Ensure the current user is active
    """
    if not current_user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return current_user

def require_role(required_role: UserRole):
    """
    Dependency factory to require a specific role

    Usage:
        @app.delete("/users/{user_id}")
        def delete_user(
            user_id: str,
            current_user: User = Depends(require_role(UserRole.ADMIN))
        ):
            # Only admins can access this
            pass
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        role_hierarchy = {
            UserRole.VIEWER: 1,
            UserRole.USER: 2,
            UserRole.ADMIN: 3
        }

        if role_hierarchy.get(current_user.role, 0) < role_hierarchy.get(required_role, 999):
            raise HTTPException(
                status_code=403,
                detail=f"Requires {required_role.value} role or higher"
            )

        return current_user

    return role_checker

async def authenticate_user_by_id(user_id: str, db: Session = None) -> User:
    """
    Authenticate user by ID (for backward compatibility with existing code)

    Args:
        user_id: User ID
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If user not found
    """
    if db is None:
        from database.session import SessionLocal
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is inactive")

        return user
    finally:
        if close_db:
            db.close()
