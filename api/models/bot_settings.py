"""Bot Settings database model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class BotSettings(Base):
    """Bot settings model for guild-specific configuration."""

    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Discord guild ID (as string to handle large numbers)
    guild_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)

    # Basic settings
    prefix: Mapped[str] = mapped_column(String(10), default="!")
    language: Mapped[str] = mapped_column(String(10), default="en")

    # Feature flags
    moderation_enabled: Mapped[bool] = mapped_column(default=True)
    logging_enabled: Mapped[bool] = mapped_column(default=True)
    welcome_enabled: Mapped[bool] = mapped_column(default=False)

    # Channel IDs (stored as strings)
    log_channel_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    welcome_channel_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mod_log_channel_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Roles
    mute_role_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    auto_role_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Custom settings as JSON
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Welcome/leave messages
    welcome_message: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    leave_message: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<BotSettings(id={self.id}, guild_id='{self.guild_id}')>"

    def to_dict(self) -> dict:
        """Convert settings to dictionary."""
        return {
            "guild_id": self.guild_id,
            "prefix": self.prefix,
            "language": self.language,
            "moderation_enabled": self.moderation_enabled,
            "logging_enabled": self.logging_enabled,
            "welcome_enabled": self.welcome_enabled,
            "log_channel_id": self.log_channel_id,
            "welcome_channel_id": self.welcome_channel_id,
            "mod_log_channel_id": self.mod_log_channel_id,
            "mute_role_id": self.mute_role_id,
            "auto_role_id": self.auto_role_id,
            "welcome_message": self.welcome_message,
            "leave_message": self.leave_message,
            "settings": self.settings or {},
        }

    @classmethod
    def create_default(cls, guild_id: str) -> "BotSettings":
        """Create default settings for a guild."""
        return cls(
            guild_id=guild_id,
            prefix="!",
            language="en",
            moderation_enabled=True,
            logging_enabled=True,
            welcome_enabled=False,
            settings={},
        )
