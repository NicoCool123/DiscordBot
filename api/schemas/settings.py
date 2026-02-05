"""Settings Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BotSettingsBase(BaseModel):
    """Base schema for bot settings."""

    prefix: str = Field(default="!", max_length=10)
    language: str = Field(default="en", max_length=10)
    moderation_enabled: bool = True
    logging_enabled: bool = True
    welcome_enabled: bool = False


class BotSettingsCreate(BotSettingsBase):
    """Schema for creating bot settings."""

    guild_id: str = Field(..., description="Discord guild ID")
    log_channel_id: Optional[str] = None
    welcome_channel_id: Optional[str] = None
    mod_log_channel_id: Optional[str] = None
    mute_role_id: Optional[str] = None
    auto_role_id: Optional[str] = None
    welcome_message: Optional[str] = Field(None, max_length=2000)
    leave_message: Optional[str] = Field(None, max_length=2000)
    settings: dict[str, Any] = {}


class BotSettingsUpdate(BaseModel):
    """Schema for updating bot settings."""

    prefix: Optional[str] = Field(None, max_length=10)
    language: Optional[str] = Field(None, max_length=10)
    moderation_enabled: Optional[bool] = None
    logging_enabled: Optional[bool] = None
    welcome_enabled: Optional[bool] = None
    log_channel_id: Optional[str] = None
    welcome_channel_id: Optional[str] = None
    mod_log_channel_id: Optional[str] = None
    mute_role_id: Optional[str] = None
    auto_role_id: Optional[str] = None
    welcome_message: Optional[str] = Field(None, max_length=2000)
    leave_message: Optional[str] = Field(None, max_length=2000)
    settings: Optional[dict[str, Any]] = None


class BotSettingsResponse(BotSettingsBase):
    """Schema for bot settings response."""

    id: int
    guild_id: str
    log_channel_id: Optional[str] = None
    welcome_channel_id: Optional[str] = None
    mod_log_channel_id: Optional[str] = None
    mute_role_id: Optional[str] = None
    auto_role_id: Optional[str] = None
    welcome_message: Optional[str] = None
    leave_message: Optional[str] = None
    settings: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GuildInfo(BaseModel):
    """Schema for Discord guild information."""

    id: str
    name: str
    icon_url: Optional[str] = None
    member_count: int
    owner_id: str
    has_settings: bool = False


class GuildListResponse(BaseModel):
    """Schema for list of guilds."""

    guilds: list[GuildInfo]
    total: int
