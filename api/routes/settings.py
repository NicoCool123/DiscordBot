"""Bot settings API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.rate_limiter import limit_api, limit_bot
from api.core.security import (
    get_api_key_or_user,
    require_permission,
)
from api.models.audit_log import AuditActions, AuditLog
from api.models.bot_settings import BotSettings
from api.models.user import User
from api.schemas.settings import (
    BotSettingsCreate,
    BotSettingsResponse,
    BotSettingsUpdate,
)

router = APIRouter()


@router.get("/{guild_id}", response_model=BotSettingsResponse)
@limit_api()
async def get_guild_settings(
    guild_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
) -> BotSettings:
    """Get settings for a specific guild.

    Args:
        guild_id: Discord guild ID
        request: FastAPI request
        db: Database session
        auth: Authentication tuple

    Returns:
        Guild settings
    """
    user, api_key, is_bot_key = auth

    # Bot or authenticated user with permission
    if not is_bot_key and (user is None or not user.has_permission("settings:read")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view settings",
        )

    result = await db.execute(
        select(BotSettings).where(BotSettings.guild_id == guild_id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settings for guild {guild_id} not found",
        )

    return settings


@router.post("", response_model=BotSettingsResponse, status_code=status.HTTP_201_CREATED)
@limit_bot()
async def create_guild_settings(
    request: Request,
    settings_data: BotSettingsCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
) -> BotSettings:
    """Create settings for a new guild.

    Args:
        request: FastAPI request
        settings_data: Settings data
        db: Database session
        auth: Authentication tuple

    Returns:
        Created settings
    """
    user, api_key, is_bot_key = auth

    # Bot or admin user
    if not is_bot_key and (user is None or not user.has_permission("settings:write")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create settings",
        )

    # Check if settings already exist
    result = await db.execute(
        select(BotSettings).where(BotSettings.guild_id == settings_data.guild_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Settings for guild {settings_data.guild_id} already exist",
        )

    # Create settings
    settings = BotSettings(
        guild_id=settings_data.guild_id,
        prefix=settings_data.prefix,
        language=settings_data.language,
        moderation_enabled=settings_data.moderation_enabled,
        logging_enabled=settings_data.logging_enabled,
        welcome_enabled=settings_data.welcome_enabled,
        log_channel_id=settings_data.log_channel_id,
        welcome_channel_id=settings_data.welcome_channel_id,
        mod_log_channel_id=settings_data.mod_log_channel_id,
        mute_role_id=settings_data.mute_role_id,
        auto_role_id=settings_data.auto_role_id,
        welcome_message=settings_data.welcome_message,
        leave_message=settings_data.leave_message,
        settings=settings_data.settings,
    )

    db.add(settings)
    await db.commit()
    await db.refresh(settings)

    return settings


@router.put("/{guild_id}", response_model=BotSettingsResponse)
@limit_api()
async def update_guild_settings(
    guild_id: str,
    request: Request,
    settings_update: BotSettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
) -> BotSettings:
    """Update settings for a guild.

    Args:
        guild_id: Discord guild ID
        request: FastAPI request
        settings_update: Settings to update
        db: Database session
        auth: Authentication tuple

    Returns:
        Updated settings
    """
    user, api_key, is_bot_key = auth

    # Bot or user with permission
    if not is_bot_key and (user is None or not user.has_permission("settings:write")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update settings",
        )

    result = await db.execute(
        select(BotSettings).where(BotSettings.guild_id == guild_id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settings for guild {guild_id} not found",
        )

    # Track changes for audit log
    changes = {}

    # Update fields
    update_data = settings_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            old_value = getattr(settings, field)
            if old_value != value:
                changes[field] = {"old": old_value, "new": value}
                setattr(settings, field, value)

    if changes:
        # Create audit log
        audit = AuditLog.create(
            action=AuditActions.BOT_SETTINGS_UPDATE,
            resource="settings",
            resource_id=guild_id,
            user_id=user.id if user else None,
            details={"changes": changes},
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)

    await db.commit()
    await db.refresh(settings)

    return settings


@router.delete("/{guild_id}")
@limit_api()
async def delete_guild_settings(
    guild_id: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("settings:write"))],
) -> dict:
    """Delete settings for a guild.

    Args:
        guild_id: Discord guild ID
        request: FastAPI request
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message
    """
    result = await db.execute(
        select(BotSettings).where(BotSettings.guild_id == guild_id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Settings for guild {guild_id} not found",
        )

    await db.delete(settings)

    # Create audit log
    audit = AuditLog.create(
        action="settings.delete",
        resource="settings",
        resource_id=guild_id,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {"message": f"Settings for guild {guild_id} deleted"}
