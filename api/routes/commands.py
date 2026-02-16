"""Command management API routes (custom + built-in toggle)."""

import asyncio
import time
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.rate_limiter import limit_api
from api.core.security import get_api_key_or_user, get_current_active_user
from api.models.audit_log import AuditActions, AuditLog
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
from api.websocket.status import broadcast_bot_event

router = APIRouter()

DISCORD_API_BASE = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20

# Cache guild access results to avoid hammering Discord API on parallel requests
# Key: (user_id, guild_id) -> (timestamp, has_access)
_user_guilds_cache: dict[int, tuple[float, list[dict]]] = {}
_user_guilds_locks: dict[int, asyncio.Lock] = {}
_USER_GUILDS_TTL = 300  # 5 Minuten
# Lock per cache key to prevent parallel Discord API calls for the same user+guild


async def verify_guild_access(user: User, guild_id: str) -> None:
    if user.is_superuser:
        return

    guilds = await _get_user_guilds(user)

    for guild in guilds:
        if guild["id"] == guild_id:
            perms = int(guild.get("permissions", 0))
            if guild.get("owner") or (perms & MANAGE_GUILD):
                return
            break

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have permission to manage this guild",
    )

async def verify_guild_member(user: User, guild_id: str) -> None:
    if user.is_superuser:
        return

    guilds = await _get_user_guilds(user)

    if any(g["id"] == guild_id for g in guilds):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not a member of this guild",
    )
# =====================================================================
# Custom Commands
# =====================================================================

@router.get("/{guild_id}")
@limit_api()
async def list_custom_commands(
    guild_id: str,
    request: Request,
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """List all custom commands for a guild."""
    user, api_key, is_bot_key = auth

    # Bot key: direct access. User: verify guild permissions.
    if not is_bot_key:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        await verify_guild_member(user, guild_id)

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

    # Audit log
    audit = AuditLog.create(
        action=AuditActions.COMMAND_CREATE,
        resource="custom_command",
        resource_id=cmd.name,
        user_id=current_user.id,
        details={
            "guild_id": guild_id,
            "command_name": cmd.name,
            "description": cmd.description,
            "ephemeral": cmd.ephemeral,
        },
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    # WebSocket broadcast for live dashboard update
    await broadcast_bot_event("command_created", {
        "guild_id": guild_id,
        "command": CustomCommandResponse.model_validate(cmd).model_dump(mode="json"),
    })

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

    # Capture old values for audit trail
    old_values = {
        "name": cmd.name,
        "description": cmd.description,
        "response": cmd.response,
        "ephemeral": cmd.ephemeral,
        "enabled": cmd.enabled,
    }

    update_data = command_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cmd, field, value)

    await db.commit()
    await db.refresh(cmd)

    # Build changes dict
    changes = {}
    for field, new_val in update_data.items():
        old_val = old_values.get(field)
        if old_val != new_val:
            changes[field] = {"old": old_val, "new": new_val}

    # Audit log
    audit = AuditLog.create(
        action=AuditActions.COMMAND_UPDATE,
        resource="custom_command",
        resource_id=cmd.name,
        user_id=current_user.id,
        details={
            "guild_id": guild_id,
            "command_name": cmd.name,
            "changes": changes,
        },
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    # WebSocket broadcast
    await broadcast_bot_event("command_updated", {
        "guild_id": guild_id,
        "command": CustomCommandResponse.model_validate(cmd).model_dump(mode="json"),
    })

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

    command_name = cmd.name  # Capture before delete
    await db.delete(cmd)
    await db.commit()

    # Audit log
    audit = AuditLog.create(
        action=AuditActions.COMMAND_DELETE,
        resource="custom_command",
        resource_id=command_name,
        user_id=current_user.id,
        details={
            "guild_id": guild_id,
            "command_name": command_name,
        },
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    # WebSocket broadcast
    await broadcast_bot_event("command_deleted", {
        "guild_id": guild_id,
        "command_id": command_id,
        "command_name": command_name,
    })

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
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """List all built-in commands with their enabled state for a guild."""
    user, api_key, is_bot_key = auth

    if not is_bot_key:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        await verify_guild_member(user, guild_id)

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


# =====================================================================
# Command Activity (no audit:read permission needed)
# =====================================================================

@router.get("/{guild_id}/activity")
@limit_api()
async def get_command_activity(
    guild_id: str,
    request: Request,
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get recent command activity for a guild (no audit:read perm needed)."""
    user, api_key, is_bot_key = auth

    if not is_bot_key:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        await verify_guild_member(user, guild_id)

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.resource == "custom_command")
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    logs = result.scalars().all()

    # Filter to this guild by checking details JSON
    activity = []
    for log in logs:
        details = log.details or {}
        log_guild = details.get("guild_id") or log.discord_guild_id
        if log_guild == guild_id:
            activity.append({
                "id": log.id,
                "action": log.action,
                "resource_id": log.resource_id,
                "details": details,
                "created_at": log.created_at.isoformat(),
            })
        if len(activity) >= 10:
            break

    return {"activity": activity, "total": len(activity)}

async def _get_user_guilds(user: User) -> list[dict]:
    if not user.discord_access_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Discord account linked",
        )

    # 1) Cache before lock
    cached = _user_guilds_cache.get(user.id)
    if cached and (time.time() - cached[0]) < _USER_GUILDS_TTL:
        return cached[1]

    # 2) Lock per user
    lock = _user_guilds_locks.get(user.id)
    if lock is None:
        lock = asyncio.Lock()
        _user_guilds_locks[user.id] = lock

    async with lock:
        # 3) Cache again inside lock (critical)
        cached = _user_guilds_cache.get(user.id)
        if cached and (time.time() - cached[0]) < _USER_GUILDS_TTL:
            return cached[1]

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 4) Retry loop for 429
            for _ in range(3):
                resp = await client.get(
                    f"{DISCORD_API_BASE}/users/@me/guilds",
                    headers={"Authorization": f"Bearer {user.discord_access_token}"},
                )

                # Token invalid/expired
                if resp.status_code in (401, 403):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Discord login expired. Reconnect Discord account.",
                    )

                # Rate limit
                if resp.status_code == 429:
                    try:
                        data = resp.json()
                        retry_after = float(data.get("retry_after", 1.0))
                    except Exception:
                        retry_after = 1.0
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Discord API temporarily unavailable. Try again.",
                    )

                guilds = resp.json()
                _user_guilds_cache[user.id] = (time.time(), guilds)
                return guilds

        # Wenn nach Retries immer noch 429:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord rate-limited. Try again in a moment.",
        )