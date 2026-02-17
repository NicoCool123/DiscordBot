"""Built-in command toggle Pydantic schemas."""

from pydantic import BaseModel


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
