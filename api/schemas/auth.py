"""Authentication Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Schema for user registration."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores and hyphens allowed)")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str = Field(..., description="Username or email")
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""

    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    is_verified: bool
    mfa_enabled: bool
    discord_id: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    roles: list[str] = []
    permissions: list[str] = []

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    display_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None


class PasswordChange(BaseModel):
    """Schema for password change."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class Token(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""

    sub: str
    exp: int
    iat: int
    type: str  # "access" or "refresh"


class RefreshToken(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str


class MFASetup(BaseModel):
    """Schema for MFA setup response."""

    secret: str
    provisioning_uri: str
    qr_code: str  # Base64 encoded QR code image


class MFAVerify(BaseModel):
    """Schema for MFA verification."""

    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def code_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("MFA code must be numeric")
        return v


class MFALogin(BaseModel):
    """Schema for login with MFA."""

    username: str
    password: str
    mfa_code: str = Field(..., min_length=6, max_length=6)
