"""Minecraft RCON Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MinecraftStatus(BaseModel):
    """Schema for Minecraft server status."""

    online: bool
    host: str
    port: int
    players_online: int = 0
    players_max: int = 0
    player_list: list[str] = []
    tps: Optional[float] = None
    version: Optional[str] = None
    last_checked: datetime


class MinecraftCommand(BaseModel):
    """Schema for Minecraft command request."""

    command: str = Field(..., min_length=1, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "command": "list"
            }
        }


class MinecraftCommandResponse(BaseModel):
    """Schema for Minecraft command response."""

    success: bool
    command: str
    response: str
    executed_at: datetime


class MinecraftStatusReport(BaseModel):
    """Schema for Minecraft status report from bot."""

    online: bool
    players: str = ""
    tps: Optional[str] = None


class MinecraftWhitelistAction(BaseModel):
    """Schema for whitelist actions."""

    action: str = Field(..., pattern="^(add|remove)$")
    player: str = Field(..., min_length=1, max_length=16)


class MinecraftLog(BaseModel):
    """Schema for Minecraft command log."""

    id: int
    command: str
    response: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    executed_at: datetime

    class Config:
        from_attributes = True


class MinecraftLogsResponse(BaseModel):
    """Schema for Minecraft logs list."""

    logs: list[MinecraftLog]
    total: int
    page: int
    per_page: int
