"""Command management API routes (custom + built-in toggle)."""

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.rate_limiter import limit_api
from api.core.security import get_current_active_user
from api.models.custom_command import CustomCommand
from api.models.command_config import CommandConfig
from api.models.user import User
from api.schemas.commands import (
    BuiltinCommandInfo,
    CommandConfigUpdate,
    CustomCommandCreate,
    CustomCommandResponse,
    CustomCommandUpdate,
)

router = APIRouter()

DISCORD_API_BASE = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20


async def verify_guild_access(user: User, guild_id: str) -> None:
    """Verify the user has MANAGE_GUILD permission for the given guild."""
    if user.is_superuser:
        return

    if not user.discord_access_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Discord account linked",
        )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{DISCORD_API_BASE}/users/@me/guilds",
            headers={"Authorization": f"Bearer {user.discord_access_token}"},
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Failed to verify guild access",
            )

        guilds = response.json()
        for guild in guilds:
            if guild["id"] == guild_id:
                perms = int(guild.get("permissions", 0))
                if guild.get("owner") or (perms & MANAGE_GUILD):
                    return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have permission to manage this guild",
    )


# =====================================================================
# Custom Commands
# =====================================================================

@router.get("/{guild_id}")
@limit_api()
async def list_custom_commands(
    guild_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """List all custom commands for a guild."""
    await verify_guild_access(current_user, guild_id)

    result = await db.execute(
        select(CustomCommand).where(CustomCommand.guild_id == guild_id)
    )
    commands = result.scalars().all()

    return {
        "commands": [CustomCommandResponse.model_validate(c) for c in commands],
        "total": len(commands),
    }


@router.post("/{guild_id}", status_code=status.HTTP_201_CREATED)
@limit_api("10/minute")
async def create_custom_command(
    guild_id: str,
    request: Request,
    command_data: CustomCommandCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomCommandResponse:
    """Create a new custom command for a guild."""
    await verify_guild_access(current_user, guild_id)

    # Check for duplicate
    result = await db.execute(
        select(CustomCommand).where(
            and_(
                CustomCommand.guild_id == guild_id,
                CustomCommand.name == command_data.name,
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Command '{command_data.name}' already exists in this guild",
        )

    cmd = CustomCommand(
        guild_id=guild_id,
        name=command_data.name,
        description=command_data.description,
        response=command_data.response,
        ephemeral=command_data.ephemeral,
        created_by=current_user.id,
    )
    db.add(cmd)
    await db.commit()
    await db.refresh(cmd)

    return CustomCommandResponse.model_validate(cmd)


@router.put("/{guild_id}/{command_id}")
@limit_api("10/minute")
async def update_custom_command(
    guild_id: str,
    command_id: int,
    request: Request,
    command_data: CustomCommandUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomCommandResponse:
    """Update a custom command."""
    await verify_guild_access(current_user, guild_id)

    result = await db.execute(
        select(CustomCommand).where(
            and_(CustomCommand.id == command_id, CustomCommand.guild_id == guild_id)
        )
    )
    cmd = result.scalar_one_or_none()
    if cmd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    update_data = command_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cmd, field, value)

    await db.commit()
    await db.refresh(cmd)

    return CustomCommandResponse.model_validate(cmd)


@router.delete("/{guild_id}/{command_id}")
@limit_api("10/minute")
async def delete_custom_command(
    guild_id: str,
    command_id: int,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a custom command."""
    await verify_guild_access(current_user, guild_id)

    result = await db.execute(
        select(CustomCommand).where(
            and_(CustomCommand.id == command_id, CustomCommand.guild_id == guild_id)
        )
    )
    cmd = result.scalar_one_or_none()
    if cmd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    await db.delete(cmd)
    await db.commit()

    return {"status": "ok", "deleted": command_id}


# =====================================================================
# Built-in Command Toggles (Phase 4)
# =====================================================================

# Known built-in commands (cog_name -> list of commands)
BUILTIN_COMMANDS: list[dict] = [
    {"name": "ban", "description": "Ban a user from the server", "cog": "moderation"},
    {"name": "unban", "description": "Unban a user", "cog": "moderation"},
    {"name": "kick", "description": "Kick a user from the server", "cog": "moderation"},
    {"name": "mute", "description": "Mute a user", "cog": "moderation"},
    {"name": "unmute", "description": "Unmute a user", "cog": "moderation"},
    {"name": "warn", "description": "Warn a user", "cog": "moderation"},
    {"name": "clear", "description": "Clear messages in a channel", "cog": "moderation"},
    {"name": "slowmode", "description": "Set channel slowmode", "cog": "moderation"},
    {"name": "mc status", "description": "Check Minecraft server status", "cog": "minecraft"},
    {"name": "mc players", "description": "List online Minecraft players", "cog": "minecraft"},
    {"name": "mc command", "description": "Send RCON command to Minecraft server", "cog": "minecraft"},
    {"name": "settings", "description": "View/change bot settings", "cog": "admin"},
    {"name": "prefix", "description": "Change bot prefix", "cog": "admin"},
    {"name": "reload", "description": "Reload bot cogs", "cog": "admin"},
]


@router.get("/{guild_id}/builtin")
@limit_api()
async def list_builtin_commands(
    guild_id: str,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """List all built-in commands with their enabled state for a guild."""
    await verify_guild_access(current_user, guild_id)

    # Get all configs for this guild
    result = await db.execute(
        select(CommandConfig).where(CommandConfig.guild_id == guild_id)
    )
    configs = {c.command_name: c.enabled for c in result.scalars().all()}

    commands = []
    for cmd in BUILTIN_COMMANDS:
        commands.append(
            BuiltinCommandInfo(
                name=cmd["name"],
                description=cmd["description"],
                cog=cmd["cog"],
                enabled=configs.get(cmd["name"], True),  # Default: enabled
            )
        )

    return {"commands": commands, "total": len(commands)}


@router.put("/{guild_id}/builtin/{command_name:path}")
@limit_api("10/minute")
async def toggle_builtin_command(
    guild_id: str,
    command_name: str,
    request: Request,
    config_data: CommandConfigUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Toggle a built-in command on or off for a guild."""
    await verify_guild_access(current_user, guild_id)

    # Verify it's a known command
    known = any(c["name"] == command_name for c in BUILTIN_COMMANDS)
    if not known:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown built-in command: {command_name}",
        )

    # Upsert config
    result = await db.execute(
        select(CommandConfig).where(
            and_(
                CommandConfig.guild_id == guild_id,
                CommandConfig.command_name == command_name,
            )
        )
    )
    config = result.scalar_one_or_none()

    if config:
        config.enabled = config_data.enabled
    else:
        config = CommandConfig(
            guild_id=guild_id,
            command_name=command_name,
            enabled=config_data.enabled,
        )
        db.add(config)

    await db.commit()

    return {"command_name": command_name, "enabled": config_data.enabled}
