"""JWT Token handling for authentication."""

from datetime import datetime, timedelta
from typing import Any, Optional

import jwt
from jwt.exceptions import PyJWTError
from pydantic import ValidationError

from api.core.config import settings
from api.schemas.auth import TokenPayload


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """Create a new access token.

    Args:
        subject: Token subject (usually user ID)
        expires_delta: Custom expiration time
        additional_claims: Additional claims to include in token

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.utcnow() + expires_delta

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    }

    if additional_claims:
        to_encode.update(additional_claims)

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a new refresh token.

    Args:
        subject: Token subject (usually user ID)
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.refresh_token_expire_days)

    expire = datetime.utcnow() + expires_delta

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    }

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str, token_type: str = "access") -> Optional[TokenPayload]:
    """Verify and decode a JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        TokenPayload if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Verify token type
        if payload.get("type") != token_type:
            return None

        # Create TokenPayload
        return TokenPayload(
            sub=payload.get("sub"),
            exp=payload.get("exp"),
            iat=payload.get("iat"),
            type=payload.get("type"),
        )

    except (PyJWTError, ValidationError):
        return None


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode a JWT token without verification (for debugging).

    Args:
        token: JWT token string

    Returns:
        Token payload as dictionary, or None if invalid
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_signature": False},
        )
    except PyJWTError:
        return None


def get_token_expiry(token: str) -> Optional[datetime]:
    """Get the expiry time of a token.

    Args:
        token: JWT token string

    Returns:
        Expiry datetime or None if invalid
    """
    payload = decode_token(token)
    if payload and "exp" in payload:
        return datetime.fromtimestamp(payload["exp"])
    return None


def is_token_expired(token: str) -> bool:
    """Check if a token is expired.

    Args:
        token: JWT token string

    Returns:
        True if expired or invalid, False otherwise
    """
    expiry = get_token_expiry(token)
    if expiry is None:
        return True
    return datetime.utcnow() > expiry
