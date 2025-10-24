"""
Encrypted Credential Management
Securely store and retrieve cloud provider credentials using Fernet encryption
"""
from cryptography.fernet import Fernet
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import json
import os
import logging

from database.models import Credential, CloudProvider
from database.session import get_db, SessionLocal

# Get encryption key from environment
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Generate key if not provided (development only!)
if not ENCRYPTION_KEY:
    logging.warning("ENCRYPTION_KEY not set! Generating temporary key (NOT for production!)")
    ENCRYPTION_KEY = Fernet.generate_key().decode()

# Initialize Fernet cipher
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_credentials(credentials: Dict[str, Any]) -> str:
    """
    Encrypt credentials dictionary to encrypted string

    Args:
        credentials: Dictionary containing credential data
                    e.g., {"aws_access_key": "AKIA...", "aws_secret_key": "..."}

    Returns:
        Encrypted string
    """
    try:
        # Convert to JSON
        json_data = json.dumps(credentials)

        # Encrypt
        encrypted = fernet.encrypt(json_data.encode())

        return encrypted.decode()

    except Exception as e:
        logging.error(f"Error encrypting credentials: {e}")
        raise ValueError("Failed to encrypt credentials")

def decrypt_credentials(encrypted_data: str) -> Dict[str, Any]:
    """
    Decrypt encrypted credentials string to dictionary

    Args:
        encrypted_data: Encrypted string

    Returns:
        Dictionary containing decrypted credentials

    Raises:
        ValueError: If decryption fails
    """
    try:
        # Decrypt
        decrypted = fernet.decrypt(encrypted_data.encode())

        # Parse JSON
        credentials = json.loads(decrypted.decode())

        return credentials

    except Exception as e:
        logging.error(f"Error decrypting credentials: {e}")
        raise ValueError("Failed to decrypt credentials")

async def store_user_credentials(
    user_id: str,
    provider: CloudProvider,
    credentials: Dict[str, Any],
    region: Optional[str] = None,
    is_default: bool = True,
    db: Optional[Session] = None
) -> Credential:
    """
    Store encrypted credentials for a user

    Args:
        user_id: User ID
        provider: Cloud provider (AWS, Azure, GCP)
        credentials: Credential dictionary
                    For AWS: {"aws_access_key": "...", "aws_secret_key": "..."}
                    For Azure: {"subscription_id": "...", "client_id": "...", "client_secret": "...", "tenant_id": "..."}
                    For GCP: {"project_id": "...", "private_key": "...", "client_email": "..."}
        region: Default region
        is_default: Set as default credentials for this provider
        db: Database session

    Returns:
        Created Credential object
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Encrypt credentials
        encrypted_data = encrypt_credentials(credentials)

        # If setting as default, unset other defaults for this provider
        if is_default:
            db.query(Credential).filter(
                Credential.user_id == user_id,
                Credential.provider == provider,
                Credential.is_default == True
            ).update({"is_default": False})

        # Create credential record
        credential = Credential(
            user_id=user_id,
            provider=provider,
            region=region,
            encrypted_data=encrypted_data,
            is_default=is_default,
            is_active=True
        )

        db.add(credential)
        db.commit()
        db.refresh(credential)

        logging.info(f"Stored credentials for user {user_id}, provider {provider.value}")

        return credential

    except Exception as e:
        db.rollback()
        logging.error(f"Error storing credentials: {e}")
        raise

    finally:
        if close_db:
            db.close()

async def get_user_credentials(
    user_id: str,
    provider: CloudProvider = CloudProvider.AWS,
    credential_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Retrieve and decrypt user credentials

    Args:
        user_id: User ID
        provider: Cloud provider
        credential_id: Specific credential ID (optional, uses default if not provided)
        db: Database session

    Returns:
        Decrypted credentials dictionary

    Raises:
        ValueError: If credentials not found
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Query for credentials
        query = db.query(Credential).filter(
            Credential.user_id == user_id,
            Credential.provider == provider,
            Credential.is_active == True
        )

        if credential_id:
            credential = query.filter(Credential.id == credential_id).first()
        else:
            # Get default credentials
            credential = query.filter(Credential.is_default == True).first()

            # If no default, get the most recent one
            if not credential:
                credential = query.order_by(Credential.created_at.desc()).first()

        if not credential:
            raise ValueError(f"No credentials found for user {user_id} and provider {provider.value}")

        # Update last used timestamp
        from datetime import datetime
        credential.last_used = datetime.utcnow()
        db.commit()

        # Decrypt and return
        decrypted = decrypt_credentials(credential.encrypted_data)

        # Add region if available
        if credential.region:
            decrypted['region'] = credential.region

        return decrypted

    finally:
        if close_db:
            db.close()

async def update_user_credentials(
    credential_id: str,
    user_id: str,
    credentials: Dict[str, Any],
    db: Optional[Session] = None
) -> Credential:
    """
    Update existing credentials

    Args:
        credential_id: Credential ID to update
        user_id: User ID (for authorization)
        credentials: New credential data
        db: Database session

    Returns:
        Updated Credential object

    Raises:
        ValueError: If credential not found or unauthorized
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.user_id == user_id
        ).first()

        if not credential:
            raise ValueError("Credential not found or unauthorized")

        # Encrypt new credentials
        encrypted_data = encrypt_credentials(credentials)

        credential.encrypted_data = encrypted_data
        from datetime import datetime
        credential.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(credential)

        logging.info(f"Updated credentials {credential_id} for user {user_id}")

        return credential

    except Exception as e:
        db.rollback()
        logging.error(f"Error updating credentials: {e}")
        raise

    finally:
        if close_db:
            db.close()

async def delete_user_credentials(
    credential_id: str,
    user_id: str,
    db: Optional[Session] = None
) -> bool:
    """
    Delete (deactivate) credentials

    Args:
        credential_id: Credential ID to delete
        user_id: User ID (for authorization)
        db: Database session

    Returns:
        True if successful

    Raises:
        ValueError: If credential not found or unauthorized
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.user_id == user_id
        ).first()

        if not credential:
            raise ValueError("Credential not found or unauthorized")

        # Soft delete - just mark as inactive
        credential.is_active = False

        db.commit()

        logging.info(f"Deleted credentials {credential_id} for user {user_id}")

        return True

    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting credentials: {e}")
        raise

    finally:
        if close_db:
            db.close()

async def list_user_credentials(
    user_id: str,
    provider: Optional[CloudProvider] = None,
    db: Optional[Session] = None
) -> list:
    """
    List all credentials for a user (without decrypting)

    Args:
        user_id: User ID
        provider: Optional filter by provider
        db: Database session

    Returns:
        List of credential metadata (without encrypted data)
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        query = db.query(Credential).filter(
            Credential.user_id == user_id,
            Credential.is_active == True
        )

        if provider:
            query = query.filter(Credential.provider == provider)

        credentials = query.order_by(Credential.created_at.desc()).all()

        # Return metadata without encrypted data
        return [
            {
                "id": cred.id,
                "provider": cred.provider.value,
                "region": cred.region,
                "is_default": cred.is_default,
                "created_at": cred.created_at.isoformat(),
                "last_used": cred.last_used.isoformat() if cred.last_used else None
            }
            for cred in credentials
        ]

    finally:
        if close_db:
            db.close()

def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key

    Returns:
        Base64-encoded encryption key (use in .env as ENCRYPTION_KEY)
    """
    key = Fernet.generate_key()
    return key.decode()

# For backward compatibility with existing code
async def get_user_credentials_legacy(user_id: str) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility
    Assumes AWS provider
    """
    return await get_user_credentials(user_id, CloudProvider.AWS)
