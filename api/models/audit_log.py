"""Audit Log database model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class AuditLog(Base):
    """Audit log model for tracking all actions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # User who performed the action (nullable for system actions)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Action details
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource: Mapped[str] = mapped_column(String(255), index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Additional details as JSON
    details: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Discord context (for bot actions)
    discord_user_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    discord_guild_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Retention and privacy
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    anonymized: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', resource='{self.resource}')>"

    @classmethod
    def create(
        cls,
        action: str,
        resource: str,
        user_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        discord_user_id: Optional[str] = None,
        discord_guild_id: Optional[str] = None,
    ) -> Optional["AuditLog"]:
        """Create an audit log entry if audit logging is enabled."""
        # Check if audit logging is enabled
        from api.core.config import settings

        if not settings.audit_log_enabled:
            return None

        # Don't store IP/User-Agent if disabled in settings
        if not settings.store_ip_addresses:
            ip_address = None
        if not settings.store_user_agents:
            user_agent = None

        return cls(
            action=action,
            resource=resource,
            user_id=user_id,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            discord_user_id=discord_user_id,
            discord_guild_id=discord_guild_id,
        )

    def anonymize(self) -> None:
        """Anonymize sensitive data in audit log."""
        self.ip_address = "0.0.0.0"
        self.user_agent = "[ANONYMIZED]"
        self.anonymized = True

    @classmethod
    def create_and_add(cls, db, **kwargs) -> None:
        """Create and add audit log to session if enabled."""
        log = cls.create(**kwargs)
        if log:
            db.add(log)


# Common audit actions
class AuditActions:
    """Audit action constants."""

    # Auth actions
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    LOGIN_FAILED = "auth.login_failed"
    PASSWORD_CHANGE = "auth.password_change"
    MFA_ENABLE = "auth.mfa_enable"
    MFA_DISABLE = "auth.mfa_disable"

    # User actions
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"

    # Bot actions
    BOT_RELOAD = "bot.reload"
    BOT_SETTINGS_UPDATE = "bot.settings_update"

    # Module actions
    MODULE_ENABLE = "module.enable"
    MODULE_DISABLE = "module.disable"
    MODULE_UPDATE = "module.update"

    # Minecraft actions
    MINECRAFT_COMMAND = "minecraft.command"

    # Command actions
    COMMAND_CREATE = "command.create"
    COMMAND_UPDATE = "command.update"
    COMMAND_DELETE = "command.delete"
    COMMAND_EXECUTE = "command.execute"

    # API actions
    API_KEY_CREATE = "api_key.create"
    API_KEY_REVOKE = "api_key.revoke"
