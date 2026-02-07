"""Command management Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CustomCommandCreate(BaseModel):
    """Schema for creating a custom command."""

    name: str = Field(..., min_length=1, max_length=32)
    description: str = Field(..., min_length=1, max_length=100)
    response: str = Field(..., min_length=1, max_length=2000)
    ephemeral: bool = False

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        v = v.lower().strip()
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Command name must be alphanumeric (hyphens and underscores allowed)")
        if v.startswith(("-", "_")):
            raise ValueError("Command name must start with a letter or number")
        return v


class CustomCommandUpdate(BaseModel):
    """Schema for updating a custom command."""

    name: Optional[str] = Field(None, min_length=1, max_length=32)
    description: Optional[str] = Field(None, min_length=1, max_length=100)
    response: Optional[str] = Field(None, min_length=1, max_length=2000)
    ephemeral: Optional[bool] = None
    enabled: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.lower().strip()
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Command name must be alphanumeric (hyphens and underscores allowed)")
        return v


class CustomCommandResponse(BaseModel):
    """Schema for custom command response."""

    id: int
    guild_id: str
    name: str
    description: str
    response: str
    ephemeral: bool
    enabled: bool
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommandConfigUpdate(BaseModel):
    """Schema for toggling a built-in command."""

    enabled: bool


class CommandConfigResponse(BaseModel):
    """Schema for command config response."""

    command_name: str
    enabled: bool

    class Config:
        from_attributes = True


class BuiltinCommandInfo(BaseModel):
    """Info about a built-in command with its enabled state."""

    name: str
    description: str
    cog: str
    enabled: bool = True
