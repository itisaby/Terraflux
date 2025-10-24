"""
Database Models for Infrastructure Provisioning Agent
SQLAlchemy ORM models for users, credentials, requests, and audit logs
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, Float, Boolean, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

Base = declarative_base()

class UserRole(enum.Enum):
    """User roles for RBAC"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class RequestStatus(enum.Enum):
    """Infrastructure request status"""
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ActionType(enum.Enum):
    """Types of infrastructure actions"""
    PROVISION = "provision"
    MODIFY = "modify"
    DESTROY = "destroy"
    LIST = "list"
    STATUS = "status"

class CloudProvider(enum.Enum):
    """Supported cloud providers"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"

class User(Base):
    """User account model"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Profile
    full_name = Column(String(255))
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime)

    # Relationships
    credentials = relationship("Credential", back_populates="user", cascade="all, delete-orphan")
    requests = relationship("InfraRequest", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role.value})>"

class Credential(Base):
    """Encrypted cloud provider credentials"""
    __tablename__ = "credentials"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Provider info
    provider = Column(SQLEnum(CloudProvider), nullable=False)
    region = Column(String(50))

    # Encrypted credentials (Fernet encrypted JSON)
    encrypted_data = Column(Text, nullable=False)

    # Metadata
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_used = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="credentials")

    def __repr__(self):
        return f"<Credential(id={self.id}, user_id={self.user_id}, provider={self.provider.value})>"

class InfraRequest(Base):
    """Infrastructure provisioning request"""
    __tablename__ = "infra_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)

    # Request details
    action = Column(SQLEnum(ActionType), nullable=False)
    original_message = Column(Text, nullable=False)
    parsed_intent = Column(JSON)  # Stores parsed intent as JSON

    # Infrastructure details
    provider = Column(SQLEnum(CloudProvider), default=CloudProvider.AWS)
    region = Column(String(50))
    environment = Column(String(50))
    resources = Column(JSON)  # List of resources to create

    # Terraform details
    workspace_path = Column(String(500))
    plan_id = Column(String(100))
    terraform_output = Column(Text)

    # Status and results
    status = Column(SQLEnum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    estimated_cost = Column(Float)
    actual_cost = Column(Float)
    error_message = Column(Text)

    # Outputs (resource IDs, IPs, etc.)
    outputs = Column(JSON)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    executed_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="requests")

    def __repr__(self):
        return f"<InfraRequest(id={self.id}, action={self.action.value}, status={self.status.value})>"

class AuditLog(Base):
    """Audit log for all infrastructure operations"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Action details
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(String(255))

    # Request details
    request_data = Column(JSON)
    response_data = Column(JSON)

    # Result
    success = Column(Boolean, nullable=False)
    error_message = Column(Text)

    # Metadata
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, success={self.success})>"

class ResourceInventory(Base):
    """Track all provisioned resources"""
    __tablename__ = "resource_inventory"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    request_id = Column(String(36), ForeignKey("infra_requests.id"), index=True)

    # Resource details
    provider = Column(SQLEnum(CloudProvider), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=False)
    resource_name = Column(String(255))

    # Location
    region = Column(String(50))
    environment = Column(String(50))

    # State
    is_active = Column(Boolean, default=True, nullable=False)
    terraform_state_id = Column(String(255))

    # Configuration
    configuration = Column(JSON)

    # Cost tracking
    estimated_monthly_cost = Column(Float)

    # Tags
    tags = Column(JSON)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    destroyed_at = Column(DateTime)

    def __repr__(self):
        return f"<ResourceInventory(id={self.id}, type={self.resource_type}, resource_id={self.resource_id})>"
