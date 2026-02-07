"""FastAPI Configuration using pydantic-settings."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    """Find the appropriate .env file.

    Priority: ENV_FILE env var > .env.local > .env.production > .env
    """
    if env_file := os.environ.get("ENV_FILE"):
        return env_file

    base = Path(__file__).resolve().parent.parent.parent
    for name in (".env.local", ".env.production", ".env"):
        path = base / name
        if path.is_file():
            return str(path)
    return ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Discord Bot API")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")

    # API Server
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_url: str = Field(default="http://localhost:8000")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/discord_bot"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # JWT Configuration
    jwt_secret_key: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    # Security
    secret_key: str = Field(..., description="Application secret key")
    allowed_hosts: str = Field(default="localhost,127.0.0.1")
    cors_origins: str = Field(default="http://localhost:8000")

    # Bot API Key
    bot_api_key: str = Field(..., description="API key for bot authentication")

    # Dashboard
    dashboard_url: str = Field(default="http://localhost:8000")

    # Discord OAuth
    discord_client_id: str = Field(default="")
    discord_client_secret: str = Field(default="")
    discord_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/discord/callback"
    )

    # Minecraft RCON
    rcon_enabled: bool = Field(default=False)
    rcon_host: str = Field(default="localhost")
    rcon_port: int = Field(default=25575)
    rcon_password: str = Field(default="")

    # Monitoring
    metrics_enabled: bool = Field(default=True)
    sentry_dsn: Optional[str] = Field(default=None)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Get allowed hosts as a list."""
        return [h.strip() for h in self.allowed_hosts.split(",")]

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
