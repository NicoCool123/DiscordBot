"""Bot management Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BotStatus(BaseModel):
    """Schema for bot status."""

    online: bool
    guild_count: int
    user_count: int
    latency_ms: float
    uptime_seconds: float
    version: str = "1.0.0"
    last_updated: datetime

    class Config:
        from_attributes = True


class BotStatusUpdate(BaseModel):
    """Schema for bot status update from bot."""

    guild_count: int = Field(..., ge=0)
    user_count: int = Field(..., ge=0)
    latency_ms: float = Field(..., ge=0)
    uptime_seconds: float = Field(..., ge=0)


class BotReload(BaseModel):
    """Schema for bot reload request."""

    cog: Optional[str] = Field(None, description="Specific cog to reload, or all if None")
    sync_commands: bool = Field(default=False, description="Sync slash commands after reload")


class BotReloadResponse(BaseModel):
    """Schema for bot reload response."""

    success: bool
    message: str
    reloaded_cogs: list[str] = []


class ModuleToggle(BaseModel):
    """Schema for enabling/disabling a module."""

    module_name: str
    guild_id: Optional[str] = Field(None, description="Guild-specific toggle")


class ModuleResponse(BaseModel):
    """Schema for module information."""

    name: str
    display_name: str
    description: Optional[str] = None
    category: str
    is_enabled: bool
    is_core: bool
    config: dict[str, Any] = {}
    required_permissions: list[str] = []
    dependencies: list[str] = []

    class Config:
        from_attributes = True


class ModuleListResponse(BaseModel):
    """Schema for list of modules."""

    modules: list[ModuleResponse]
    total: int


class BotLogEntry(BaseModel):
    """Schema for bot log entry."""

    level: str = Field(..., pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    message: str
    extra: dict[str, Any] = {}
    timestamp: Optional[datetime] = None


class BotAuditEntry(BaseModel):
    """Schema for bot audit log entry."""

    action: str
    resource: str
    user_id: Optional[str] = None
    guild_id: Optional[str] = None
    details: dict[str, Any] = {}
