"""Security utilities and authentication dependencies."""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.core.database import get_db
from api.core.jwt_handler import verify_token
from api.models.user import User
from api.models.api_key import APIKey

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
) -> User:
    """Get the current authenticated user from JWT token.

    Args:
        request: FastAPI request object
        db: Database session
        credentials: Bearer token credentials

    Returns:
        Authenticated User object

    Raises:
        HTTPException: If authentication fails
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_payload = verify_token(credentials.credentials)
    if token_payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    result = await db.execute(select(User).where(User.id == int(token_payload.sub)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get the current active user.

    Args:
        current_user: Current authenticated user

    Returns:
        Active User object

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Get the current superuser.

    Args:
        current_user: Current active user

    Returns:
        Superuser object

    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


async def verify_api_key(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key: Annotated[Optional[str], Depends(api_key_header)],
) -> Optional[APIKey]:
    """Verify an API key.

    Args:
        db: Database session
        api_key: API key from header

    Returns:
        APIKey object if valid, None otherwise
    """
    if api_key is None:
        return None

    # Check for bot API key (simple string comparison for bot)
    if api_key == settings.bot_api_key:
        return None  # Bot API key is valid but returns None (special case)

    # Hash the key and look it up
    key_hash = get_password_hash(api_key)

    # For API keys, we need to check by prefix first
    key_prefix = api_key[:8] if len(api_key) >= 8 else api_key

    result = await db.execute(
        select(APIKey).where(
            APIKey.key_prefix == key_prefix,
            APIKey.is_active == True,
        )
    )
    db_key = result.scalar_one_or_none()

    if db_key is None:
        return None

    # Verify the full key
    if not verify_password(api_key, db_key.key_hash):
        return None

    # Check expiration
    if db_key.is_expired:
        return None

    # Update usage stats
    db_key.last_used_at = datetime.utcnow()
    db_key.usage_count += 1
    await db.commit()

    return db_key


async def get_api_key_or_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    api_key: Annotated[Optional[str], Depends(api_key_header)],
) -> tuple[Optional[User], Optional[APIKey], bool]:
    """Get either a user from JWT or an API key.

    Args:
        request: FastAPI request
        db: Database session
        credentials: Bearer token
        api_key: API key header

    Returns:
        Tuple of (User or None, APIKey or None, is_bot_key)
    """
    # Check for bot API key first
    if api_key == settings.bot_api_key:
        return None, None, True

    # Check for user JWT
    if credentials is not None:
        token_payload = verify_token(credentials.credentials)
        if token_payload is not None:
            result = await db.execute(select(User).where(User.id == int(token_payload.sub)))
            user = result.scalar_one_or_none()
            if user is not None and user.is_active:
                return user, None, False

    # Check for API key
    if api_key is not None:
        key = await verify_api_key(db, api_key)
        if key is not None:
            return None, key, False

    return None, None, False


def require_permission(permission: str):
    """Dependency factory for requiring a specific permission.

    Args:
        permission: Required permission string

    Returns:
        Dependency function
    """

    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )
        return current_user

    return permission_checker


def require_any_permission(permissions: list[str]):
    """Dependency factory for requiring any of the specified permissions.

    Args:
        permissions: List of permission strings (any one is sufficient)

    Returns:
        Dependency function
    """

    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if not current_user.has_any_permission(permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: one of {permissions} required",
            )
        return current_user

    return permission_checker
