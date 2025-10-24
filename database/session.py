"""
Database session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base
import os
from typing import Generator
import logging

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://infraagent:infraagent@localhost:5432/infraagent"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true"
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database - create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")
        raise

def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI
    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_test_user(db: Session, username: str = "admin", password: str = "admin123"):
    """Create a test user for development"""
    from security.auth import hash_password
    from .models import User, UserRole

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        logging.info(f"User {username} already exists")
        return existing_user

    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password(password),
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logging.info(f"Created test user: {username}")
    return user
