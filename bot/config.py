"""Bot Configuration using pydantic-settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Bot configuration settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Discord Configuration
    discord_token: str = Field(..., description="Discord bot token")
    discord_prefix: str = Field(default="!", description="Default command prefix")

    # API Configuration
    api_url: str = Field(default="http://localhost:8000", description="Backend API URL")
    bot_api_key: str = Field(..., description="API key for bot-backend communication")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/discord_bot",
        description="Database connection URL",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format: json or text")
    log_file: Optional[str] = Field(default=None, description="Log file path")

    # Minecraft RCON
    rcon_enabled: bool = Field(default=False, description="Enable RCON integration")
    rcon_host: str = Field(default="localhost", description="RCON server host")
    rcon_port: int = Field(default=25575, description="RCON server port")
    rcon_password: str = Field(default="", description="RCON password")

    # Feature Flags
    debug: bool = Field(
        default=False,
        description="Debug mode",
        env="BOT_DEBUG"   # <--- FIXED
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug


@lru_cache()
def get_settings() -> BotSettings:
    """Get cached settings instance."""
    return BotSettings()


settings = get_settings()