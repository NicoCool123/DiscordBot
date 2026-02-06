from datetime import datetime
from typing import Annotated, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.core.database import get_db
from api.core.jwt_handler import verify_token
from api.models.user import User
from api.models.api_key import APIKey

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_payload = verify_token(credentials.credentials)
    if token_payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == int(token_payload.sub)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


async def get_current_superuser(current_user: Annotated[User, Depends(get_current_active_user)]) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user

async def get_api_key_or_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key: Annotated[Optional[str], Depends(api_key_header)] = None,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)] = None,
):
    """
    Liefert ein Tuple (User, APIKey, is_bot_key)
    """
    user = None
    bot_key = False
    api_key_obj = None

    # Prüfe API Key Header
    if api_key:
        result = await db.execute(select(APIKey).where(APIKey.key == api_key))
        api_key_obj = result.scalar_one_or_none()
        if api_key_obj and api_key_obj.is_bot:
            bot_key = True

    # Prüfe Bearer Token
    if credentials and not bot_key:
        token_payload = verify_token(credentials.credentials)
        if token_payload:
            result = await db.execute(select(User).where(User.id == int(token_payload.sub)))
            user = result.scalar_one_or_none()

    return (user, api_key_obj, bot_key)

def require_permission(permission: str):
    """
    Prüft, ob der aktuelle User die Berechtigung hat oder Superuser ist.
    Benutzung in Routen: Depends(require_permission("permission_name"))
    """
    async def dependency(user: User = Depends(get_current_active_user)):
        # Beispiel: user.permissions als Liste von Strings
        user_permissions = getattr(user, "permissions", [])
        if permission not in user_permissions and not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return user
    return dependency