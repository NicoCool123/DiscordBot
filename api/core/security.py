from datetime import datetime
from typing import Annotated, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.core.jwt_handler import verify_token
from api.core.database import get_db
from api.models.user import User
from api.models.api_key import APIKey

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    """Get active user from JWT token."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == int(payload.sub)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


async def get_api_key_or_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    api_key: Annotated[Optional[str], Depends(api_key_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> tuple[Optional[User], Optional[APIKey], bool]:
    """Return (user, api_key, is_bot_key)."""
    # Bot API Key
    if api_key == settings.bot_api_key:
        return None, None, True

    # User JWT
    if credentials:
        payload = verify_token(credentials.credentials)
        if payload:
            result = await db.execute(select(User).where(User.id == int(payload.sub)))
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user, None, False

    # API Key
    if api_key:
        result = await db.execute(
            select(APIKey).where(APIKey.key_prefix == api_key[:8], APIKey.is_active == True)
        )
        key = result.scalar_one_or_none()
        if key and verify_password(api_key, key.key_hash) and not key.is_expired:
            key.last_used_at = datetime.utcnow()
            key.usage_count += 1
            await db.commit()
            return None, key, False

    return None, None, False


def require_permission(permission: str):
    async def checker(user: Annotated[User, Depends(get_current_user)]):
        if user.is_superuser:
            return user
        if not getattr(user, "has_permission", lambda x: False)(permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission '{permission}' required")
        return user
    return checker