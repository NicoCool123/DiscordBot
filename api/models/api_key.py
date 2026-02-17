"""API Key database model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class APIKey(Base):
    """API Key model for bot and external service authentication."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Key identification
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Key hash (never store plain key)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Key prefix for identification (first 8 chars of key)
    key_prefix: Mapped[str] = mapped_column(String(8), index=True)

    # Owner
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Permissions
    permissions: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Rate limiting
    rate_limit: Mapped[int] = mapped_column(default=100)  # requests per minute
    rate_limit_window: Mapped[int] = mapped_column(default=60)  # seconds

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, name='{self.name}', prefix='{self.key_prefix}')>"

    @property
    def is_expired(self) -> bool:
        """Check if the API key is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired)."""
        return self.is_active and not self.is_expired

    def has_permission(self, permission: str) -> bool:
        """Check if the API key has a specific permission."""
        if not self.permissions:
            return False
        # Check for wildcard
        if "*" in self.permissions:
            return True
        return permission in self.permissions

    def to_dict(self) -> dict:
        """Convert API key to dictionary (without sensitive data)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "key_prefix": self.key_prefix,
            "permissions": self.permissions or [],
            "rate_limit": self.rate_limit,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat(),
        }
