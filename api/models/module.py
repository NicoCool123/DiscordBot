"""Module database model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class Module(Base):
    """Module model for bot module management."""

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Module identification
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Module category
    category: Mapped[str] = mapped_column(String(50), default="general")

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)  # Core modules can't be disabled

    # Configuration
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    default_config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Required permissions
    required_permissions: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Dependencies
    dependencies: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Module(id={self.id}, name='{self.name}')>"

    def to_dict(self) -> dict:
        """Convert module to dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "is_enabled": self.is_enabled,
            "is_core": self.is_core,
            "config": self.config or {},
            "required_permissions": self.required_permissions or [],
            "dependencies": self.dependencies or [],
        }


# Default modules
DEFAULT_MODULES = [
    {
        "name": "admin",
        "display_name": "Administration",
        "description": "Core administrative commands",
        "category": "core",
        "is_core": True,
        "is_enabled": True,
        "required_permissions": ["bot:admin"],
    },
    {
        "name": "moderation",
        "display_name": "Moderation",
        "description": "Server moderation commands (ban, kick, mute, warn)",
        "category": "moderation",
        "is_core": False,
        "is_enabled": True,
        "required_permissions": ["bot:write"],
    },
    {
        "name": "minecraft",
        "display_name": "Minecraft Integration",
        "description": "Minecraft server RCON integration",
        "category": "integration",
        "is_core": False,
        "is_enabled": False,
        "required_permissions": ["minecraft:command"],
        "config": {
            "rcon_enabled": False,
            "allowed_commands": ["list", "say", "whitelist"],
            "blocked_commands": ["stop", "restart", "op", "deop", "ban-ip"],
        },
    },
]
