"""Command configuration model for toggling built-in commands per guild."""

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class CommandConfig(Base):
    """Per-guild toggle for built-in bot commands."""

    __tablename__ = "command_configs"
    __table_args__ = (
        UniqueConstraint("guild_id", "command_name", name="uq_command_configs_guild_cmd"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[str] = mapped_column(String(20), index=True)
    command_name: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<CommandConfig(guild={self.guild_id}, cmd='{self.command_name}', enabled={self.enabled})>"
