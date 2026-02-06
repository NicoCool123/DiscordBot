"""Role database models for RBAC."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base

if TYPE_CHECKING:
    from api.models.user import User


class Role(Base):
    """Role model for RBAC."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Permissions as JSON array
    permissions: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"


class UserRole(Base):
    """Association table for User-Role many-to-many relationship."""

    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )

    # When the role was assigned
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"


# Default permissions
class Permissions:
    """Permission constants."""

    # User permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"

    # Bot permissions
    BOT_READ = "bot:read"
    BOT_WRITE = "bot:write"
    BOT_RELOAD = "bot:reload"
    BOT_ADMIN = "bot:admin"

    # Settings permissions
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"

    # Module permissions
    MODULE_READ = "module:read"
    MODULE_ENABLE = "module:enable"
    MODULE_DISABLE = "module:disable"

    # Minecraft permissions
    MINECRAFT_READ = "minecraft:read"
    MINECRAFT_COMMAND = "minecraft:command"

    # Audit permissions
    AUDIT_READ = "audit:read"

    # Dashboard permissions
    DASHBOARD_VIEW = "dashboard:view"
    DASHBOARD_METRICS = "dashboard:metrics"

    @classmethod
    def all(cls) -> list[str]:
        """Get all permission values."""
        return [
            v for k, v in vars(cls).items() if not k.startswith("_") and isinstance(v, str)
        ]


# Default roles
DEFAULT_ROLES = [
    {
        "name": "admin",
        "description": "Full administrative access",
        "permissions": Permissions.all(),
    },
    {
        "name": "moderator",
        "description": "Bot and settings management",
        "permissions": [
            Permissions.BOT_READ,
            Permissions.BOT_WRITE,
            Permissions.BOT_RELOAD,
            Permissions.SETTINGS_READ,
            Permissions.SETTINGS_WRITE,
            Permissions.MODULE_READ,
            Permissions.MODULE_ENABLE,
            Permissions.MODULE_DISABLE,
            Permissions.AUDIT_READ,
            Permissions.DASHBOARD_VIEW,
            Permissions.DASHBOARD_METRICS,
        ],
    },
    {
        "name": "viewer",
        "description": "Read-only access",
        "permissions": [
            Permissions.BOT_READ,
            Permissions.SETTINGS_READ,
            Permissions.MODULE_READ,
            Permissions.DASHBOARD_VIEW,
        ],
    },
]
