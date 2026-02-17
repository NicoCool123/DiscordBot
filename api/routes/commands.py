"""Built-in command toggle API routes."""

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
from api.models.command_config import CommandConfig
from api.models.user import User
from api.schemas.commands import (
    BuiltinCommandInfo,
    CommandConfigUpdate,
)

router = APIRouter()

DISCORD_API_BASE = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20

# Cache guild access results to avoid hammering Discord API on parallel requests
_user_guilds_cache: dict[int, tuple[float, list[dict]]] = {}
_user_guilds_locks: dict[int, asyncio.Lock] = {}
_USER_GUILDS_TTL = 300  # 5 minutes


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
# Built-in Command Toggles
# =====================================================================

BUILTIN_COMMANDS: list[dict] = [
    # Moderation commands
    {"name": "ban", "description": "Ban a user from the server", "cog": "moderation"},
    {"name": "unban", "description": "Unban a user", "cog": "moderation"},
    {"name": "kick", "description": "Kick a user from the server", "cog": "moderation"},
    {"name": "mute", "description": "Mute a user", "cog": "moderation"},
    {"name": "unmute", "description": "Unmute a user", "cog": "moderation"},
    {"name": "warn", "description": "Warn a user", "cog": "moderation"},
    {"name": "clear", "description": "Clear messages in a channel", "cog": "moderation"},
    {"name": "slowmode", "description": "Set channel slowmode", "cog": "moderation"},
    # Minecraft commands
    {"name": "mc status", "description": "Check Minecraft server status", "cog": "minecraft"},
    {"name": "mc players", "description": "List online Minecraft players", "cog": "minecraft"},
    {"name": "mc command", "description": "Send RCON command to Minecraft server", "cog": "minecraft"},
    # Admin commands
    {"name": "settings", "description": "View/change bot settings", "cog": "admin"},
    {"name": "prefix", "description": "Change bot prefix", "cog": "admin"},
    {"name": "reload", "description": "Reload bot cogs", "cog": "admin"},
    # Utility commands
    {"name": "util serverinfo", "description": "Show server information", "cog": "utility"},
    {"name": "util userinfo", "description": "Show user information", "cog": "utility"},
    {"name": "util avatar", "description": "Show user avatar", "cog": "utility"},
    {"name": "util ping", "description": "Check bot latency", "cog": "utility"},
    {"name": "util poll", "description": "Create a poll", "cog": "utility"},
    # Auto-moderation commands
    {"name": "automod filter-add", "description": "Add word to filter", "cog": "automod"},
    {"name": "automod filter-remove", "description": "Remove word from filter", "cog": "automod"},
    {"name": "automod filter-list", "description": "List filtered words", "cog": "automod"},
    {"name": "automod logs", "description": "View recent mod actions", "cog": "automod"},
    {"name": "automod spam-protection", "description": "Toggle spam protection", "cog": "automod"},
    {"name": "automod raid-mode", "description": "Enable raid mode", "cog": "automod"},
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

                if resp.status_code in (401, 403):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Discord login expired. Reconnect Discord account.",
                    )

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

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord rate-limited. Try again in a moment.",
        )
