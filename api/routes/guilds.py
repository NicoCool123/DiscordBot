"""Guild management API routes."""

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.rate_limiter import limit_api
from api.core.security import get_current_active_user
from api.models.bot_settings import BotSettings
from api.models.user import User

router = APIRouter()

DISCORD_API_BASE = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20  # Discord MANAGE_GUILD permission bit


@router.get("/")
@limit_api()
async def get_user_guilds(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get guilds the user can manage (has MANAGE_GUILD permission)."""
    if not current_user.discord_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Discord account linked. Please login with Discord.",
        )

    # Fetch guilds from Discord API
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{DISCORD_API_BASE}/users/@me/guilds",
            headers={"Authorization": f"Bearer {current_user.discord_access_token}"},
        )

        if response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Discord token expired. Please re-login with Discord.",
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch guilds from Discord",
            )

        all_guilds = response.json()

    # Filter to guilds where user has MANAGE_GUILD permission
    manageable = []
    for guild in all_guilds:
        perms = int(guild.get("permissions", 0))
        if guild.get("owner") or (perms & MANAGE_GUILD):
            manageable.append(guild)

    # Check which guilds the bot is in
    result = await db.execute(select(BotSettings.guild_id))
    bot_guild_ids = {row[0] for row in result.all()}

    guilds = []
    for g in manageable:
        guilds.append({
            "id": g["id"],
            "name": g["name"],
            "icon": g.get("icon"),
            "owner": g.get("owner", False),
            "bot_in_guild": g["id"] in bot_guild_ids,
        })

    return {"guilds": guilds, "total": len(guilds)}
