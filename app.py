"""
Infrastructure Provisioning Agent - Main Application
FastAPI backend with authentication, database, and agent integration
"""
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import os
from datetime import datetime
import re
from email_validator import validate_email, EmailNotValidError
 
# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import application modules
from agent.main import InfraAgent
from security.auth import (
    authenticate_user, get_current_user, create_access_token,
    hash_password, authenticate_user as auth_user_db
)
from security.password_validator import validate_password_strength
from security.credentials import (
    store_user_credentials, get_user_credentials,
    list_user_credentials, delete_user_credentials
)
from security.rbac import Permission, check_permission
from database.models import User, InfraRequest, AuditLog, CloudProvider
from database.session import get_db, init_db

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="Infrastructure Provisioning Agent",
    description="AI-powered conversational infrastructure management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Get CORS origins from environment
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []

if not ALLOWED_ORIGINS:
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("ALLOWED_ORIGINS must be set in production environment")
    # Development default
    ALLOWED_ORIGINS = ["http://localhost:8501", "http://localhost:3000", "http://127.0.0.1:8501", "http://127.0.0.1:3000"]
    logger.warning("Using default CORS origins for development")

# Import security middleware
from security.middleware import (
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    SecureErrorHandlingMiddleware,
    AuditLoggingMiddleware
)

# Add middleware (order matters - they wrap in reverse order)
# 1. CORS (most outer)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# 2. Security headers
app.add_middleware(SecurityHeadersMiddleware)

# 3. Request size limiting
max_request_size = int(os.getenv("MAX_REQUEST_SIZE_MB", "10")) * 1024 * 1024
app.add_middleware(RequestSizeLimitMiddleware, max_request_size=max_request_size)

# 4. Secure error handling
app.add_middleware(SecureErrorHandlingMiddleware)

# 5. Audit logging (most inner - logs actual requests)
app.add_middleware(AuditLoggingMiddleware)

# Initialize agent
infra_agent = InfraAgent()

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str
    role: str

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    plan: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = False
    estimated_cost: Optional[float] = None
    action_id: Optional[str] = None

class CredentialRequest(BaseModel):
    provider: str
    credentials: Dict[str, Any]
    region: Optional[str] = None
    is_default: bool = True

class ConfirmActionRequest(BaseModel):
    action_id: str

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("Starting Infrastructure Provisioning Agent...")

    try:
        # Initialize database
        init_db()
        logger.info("Database initialized")

        # Verify database connectivity
        from database.session import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            logger.info("Database connectivity verified")
        finally:
            db.close()

    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        # Exit the application if database is not available
        raise RuntimeError("Cannot start application without database connection") from e

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

# Authentication endpoints
@app.post("/auth/login", response_model=LoginResponse)
@limiter.limit("5/minute")  # Max 5 login attempts per minute
async def login(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """
    User login endpoint
    Returns JWT access token
    """
    try:
        user = auth_user_db(db, login_data.username, login_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )

        # Create access token
        access_token = create_access_token(data={"sub": user.id})

        # Log authentication
        audit_log = AuditLog(
            user_id=user.id,
            action="login",
            success=True,
            timestamp=datetime.utcnow()
        )
        db.add(audit_log)
        db.commit()

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user_id=user.id,
            username=user.username,
            role=user.role.value
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/auth/register")
@limiter.limit("3/hour")  # Max 3 registrations per hour per IP
async def register(
    request: Request,
    username: str,
    password: str,
    email: str,
    full_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Register new user with password strength and email validation"""
    try:
        # Validate username format
        if not re.match(r'^[a-zA-Z0-9_-]{3,30}$', username):
            raise HTTPException(
                status_code=400,
                detail="Username must be 3-30 characters and contain only letters, numbers, underscores, and hyphens"
            )

        # Validate email format
        try:
            validated_email = validate_email(email, check_deliverability=False)
            email = validated_email.normalized
        except EmailNotValidError as e:
            raise HTTPException(status_code=400, detail=f"Invalid email address: {str(e)}") from e

        # Validate password strength
        is_valid, error_message = validate_password_strength(password, username)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_message)

        # Check if username exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")

        # Check if email exists
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create user
        from database.models import UserRole
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=UserRole.USER,
            is_active=True
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"New user registered: {username}")

        return {"message": "User registered successfully", "user_id": user.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")

# Chat endpoints
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Main chat endpoint for infrastructure requests
    """
    try:
        # Check permission
        check_permission(current_user, Permission.VIEW_INFRASTRUCTURE)

        # Process request through agent
        response = await infra_agent.process_request(
            message=request.message,
            user=current_user,
            session_id=request.session_id
        )

        # Log request
        infra_request = InfraRequest(
            user_id=current_user.id,
            session_id=request.session_id,
            original_message=request.message,
            action=response.get('action', 'unknown'),
            status='pending'
        )
        db.add(infra_request)
        db.commit()

        return ChatResponse(**response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/confirm-action")
async def confirm_action(
    request: ConfirmActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm and execute infrastructure action
    """
    try:
        # Check permission
        check_permission(current_user, Permission.CREATE_INFRASTRUCTURE)

        # Execute action
        result = await infra_agent.execute_action(request.action_id, current_user)

        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="confirm_infrastructure_action",
            resource_type="infrastructure",
            resource_id=request.action_id,
            success=result.get('success', False),
            timestamp=datetime.utcnow()
        )
        db.add(audit_log)
        db.commit()

        return {"status": "success", "result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Confirm action error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Credential management endpoints
@app.post("/credentials/store")
async def store_credentials(
    request: CredentialRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Store cloud provider credentials"""
    try:
        check_permission(current_user, Permission.MANAGE_CREDENTIALS)

        provider = CloudProvider(request.provider)

        credential = await store_user_credentials(
            user_id=current_user.id,
            provider=provider,
            credentials=request.credentials,
            region=request.region,
            is_default=request.is_default,
            db=db
        )

        return {
            "message": "Credentials stored successfully",
            "credential_id": credential.id
        }

    except Exception as e:
        logger.error(f"Store credentials error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/credentials/list")
async def list_credentials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's stored credentials"""
    try:
        check_permission(current_user, Permission.VIEW_CREDENTIALS)

        credentials = await list_user_credentials(current_user.id, db=db)
        return {"credentials": credentials}

    except Exception as e:
        logger.error(f"List credentials error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Resource management endpoints
@app.get("/resources")
async def list_resources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's infrastructure resources"""
    try:
        check_permission(current_user, Permission.VIEW_INFRASTRUCTURE)

        from database.models import ResourceInventory
        resources = db.query(ResourceInventory).filter(
            ResourceInventory.user_id == current_user.id,
            ResourceInventory.is_active == True
        ).all()

        return {
            "resources": [
                {
                    "id": r.id,
                    "type": r.resource_type,
                    "name": r.resource_name,
                    "resource_id": r.resource_id,
                    "region": r.region,
                    "environment": r.environment,
                    "cost": r.estimated_monthly_cost,
                    "created_at": r.created_at.isoformat()
                }
                for r in resources
            ]
        }

    except Exception as e:
        logger.error(f"List resources error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Admin endpoints
@app.get("/admin/users")
async def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all users (admin only)"""
    try:
        check_permission(current_user, Permission.VIEW_USERS)

        users = db.query(User).all()

        return {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "role": u.role.value,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat()
                }
                for u in users
            ]
        }

    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Run application
if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
