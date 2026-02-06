"""Authentication API routes."""

import base64
import io
from datetime import datetime
from typing import Annotated

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.core.database import get_db
from api.core.jwt_handler import create_access_token, create_refresh_token, verify_token
from api.core.rate_limiter import limit_auth
from api.core.security import (
    get_current_active_user,
    get_password_hash,
    verify_password,
)
from api.models.audit_log import AuditActions, AuditLog
from api.models.user import User
from api.schemas.auth import (
    MFALogin,
    MFASetup,
    MFAVerify,
    PasswordChange,
    RefreshToken,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limit_auth("3/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Register a new user.

    Args:
        request: FastAPI request
        user_data: User registration data
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if user exists
    result = await db.execute(
        select(User).where(
            or_(
                User.username == user_data.username.lower(),
                User.email == user_data.email.lower(),
            )
        )
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.username == user_data.username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = User(
        username=user_data.username.lower(),
        email=user_data.email.lower(),
        password_hash=get_password_hash(user_data.password),
        is_active=True,
        is_superuser=False,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create audit log
    audit = AuditLog.create(
        action=AuditActions.USER_CREATE,
        resource="user",
        user_id=user.id,
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return user


@router.post("/login", response_model=Token)
@limit_auth("5/minute")
async def login(
    request: Request,
    credentials: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Authenticate user and return tokens.

    Args:
        request: FastAPI request
        credentials: Login credentials
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by username or email
    result = await db.execute(
        select(User).where(
            or_(
                User.username == credentials.username.lower(),
                User.email == credentials.username.lower(),
            )
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(credentials.password, user.password_hash):
        # Log failed attempt
        audit = AuditLog.create(
            action=AuditActions.LOGIN_FAILED,
            resource="auth",
            details={"username": credentials.username},
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Check if MFA is required
    if user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="MFA verification required",
            headers={"X-MFA-Required": "true"},
        )

    # Update last login
    user.last_login = datetime.utcnow()

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # Log successful login
    audit = AuditLog.create(
        action=AuditActions.LOGIN,
        resource="auth",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/login/mfa", response_model=Token)
@limit_auth("5/minute")
async def login_with_mfa(
    request: Request,
    credentials: MFALogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Authenticate user with MFA and return tokens.

    Args:
        request: FastAPI request
        credentials: Login credentials with MFA code
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials or MFA code are invalid
    """
    # Find user
    result = await db.execute(
        select(User).where(
            or_(
                User.username == credentials.username.lower(),
                User.email == credentials.username.lower(),
            )
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Verify MFA code
    if user.mfa_enabled and user.mfa_secret:
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(credentials.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code",
            )

    # Update last login
    user.last_login = datetime.utcnow()

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # Log successful login
    audit = AuditLog.create(
        action=AuditActions.LOGIN,
        resource="auth",
        user_id=user.id,
        details={"mfa_used": True},
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/refresh", response_model=Token)
@limit_auth("10/minute")
async def refresh_tokens(
    request: Request,
    refresh_data: RefreshToken,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    token_payload = verify_token(refresh_data.refresh_token, token_type="refresh")

    if token_payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    result = await db.execute(select(User).where(User.id == int(token_payload.sub)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/logout")
async def logout(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Logout user (client should discard tokens).

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message
    """
    # Log logout
    audit = AuditLog.create(
        action=AuditActions.LOGOUT,
        resource="auth",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        User information
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Update current user profile.

    Args:
        user_update: Fields to update
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user
    """
    if user_update.display_name is not None:
        current_user.display_name = user_update.display_name

    if user_update.email is not None:
        # Check if email is already taken
        result = await db.execute(
            select(User).where(
                User.email == user_update.email.lower(),
                User.id != current_user.id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        current_user.email = user_update.email.lower()

    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.post("/password/change")
async def change_password(
    request: Request,
    password_data: PasswordChange,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Change current user's password.

    Args:
        request: FastAPI request
        password_data: Current and new password
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If current password is incorrect
    """
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = get_password_hash(password_data.new_password)

    # Log password change
    audit = AuditLog.create(
        action=AuditActions.PASSWORD_CHANGE,
        resource="auth",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {"message": "Password changed successfully"}


@router.post("/mfa/enable", response_model=MFASetup)
async def enable_mfa(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Enable MFA for current user.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        MFA setup information including QR code

    Raises:
        HTTPException: If MFA is already enabled
    """
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    # Generate secret
    secret = pyotp.random_base32()
    current_user.mfa_secret = secret

    # Generate provisioning URI
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="Discord Bot Dashboard",
    )

    # Generate QR code
    import qrcode

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    await db.commit()

    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "qr_code": f"data:image/png;base64,{qr_base64}",
    }


@router.post("/mfa/verify")
async def verify_mfa(
    request: Request,
    mfa_data: MFAVerify,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Verify MFA code and activate MFA.

    Args:
        request: FastAPI request
        mfa_data: MFA verification code
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If MFA code is invalid
    """
    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup not initiated",
        )

    totp = pyotp.TOTP(current_user.mfa_secret)
    if not totp.verify(mfa_data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code",
        )

    current_user.mfa_enabled = True

    # Log MFA enable
    audit = AuditLog.create(
        action=AuditActions.MFA_ENABLE,
        resource="auth",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {"message": "MFA enabled successfully"}


@router.post("/mfa/disable")
async def disable_mfa(
    request: Request,
    mfa_data: MFAVerify,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Disable MFA for current user.

    Args:
        request: FastAPI request
        mfa_data: MFA verification code
        current_user: Current authenticated user
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If MFA is not enabled or code is invalid
    """
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled",
        )

    totp = pyotp.TOTP(current_user.mfa_secret)
    if not totp.verify(mfa_data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MFA code",
        )

    current_user.mfa_enabled = False
    current_user.mfa_secret = None

    # Log MFA disable
    audit = AuditLog.create(
        action=AuditActions.MFA_DISABLE,
        resource="auth",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {"message": "MFA disabled successfully"}
