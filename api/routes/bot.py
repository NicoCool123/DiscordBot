"""Bot management API routes."""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.core.database import get_db
from api.core.rate_limiter import limit_api, limit_bot
from api.core.security import (
    get_api_key_or_user,
    get_current_active_user,
    require_permission,
)
from api.models.audit_log import AuditActions, AuditLog
from api.models.module import Module
from api.models.user import User
from api.models.api_key import APIKey
from api.schemas.bot import (
    BotAuditEntry,
    BotLogEntry,
    BotReload,
    BotReloadResponse,
    BotStatus,
    BotStatusUpdate,
    ModuleListResponse,
    ModuleResponse,
    ModuleToggle,
)

router = APIRouter()

# In-memory bot status (in production, use Redis)
_bot_status: dict = {
    "online": False,
    "guild_count": 0,
    "user_count": 0,
    "latency_ms": 0.0,
    "uptime_seconds": 0.0,
    "version": "1.0.0",
    "last_updated": datetime.utcnow(),
}


@router.get("/status", response_model=BotStatus)
@limit_api()
async def get_bot_status(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("bot:read"))],
) -> dict:
    """Get current bot status.

    Args:
        request: FastAPI request
        current_user: Current authenticated user

    Returns:
        Bot status information
    """
    return _bot_status


@router.post("/status")
@limit_bot()
async def update_bot_status(
    request: Request,
    status_update: BotStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
) -> dict:
    """Update bot status (called by bot).

    Args:
        request: FastAPI request
        status_update: Status update data
        db: Database session
        auth: Authentication tuple (user, api_key, is_bot_key)

    Returns:
        Success acknowledgment
    """
    user, api_key, is_bot_key = auth

    # Only bot or admin can update status
    if not is_bot_key and (user is None or not user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update bot status",
        )

    global _bot_status
    _bot_status.update({
        "online": True,
        "guild_count": status_update.guild_count,
        "user_count": status_update.user_count,
        "latency_ms": status_update.latency_ms,
        "uptime_seconds": status_update.uptime_seconds,
        "last_updated": datetime.utcnow(),
    })

    return {"status": "ok"}


@router.post("/reload", response_model=BotReloadResponse)
@limit_api("5/minute")
async def reload_bot(
    request: Request,
    reload_data: BotReload,
    current_user: Annotated[User, Depends(require_permission("bot:reload"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Request bot reload (signal to bot via WebSocket or polling).

    Args:
        request: FastAPI request
        reload_data: Reload configuration
        current_user: Current authenticated user
        db: Database session

    Returns:
        Reload response
    """
    # In a real implementation, this would signal the bot via WebSocket
    # For now, we just log the request

    cogs = [reload_data.cog] if reload_data.cog else ["all"]

    # Create audit log
    audit = AuditLog.create(
        action=AuditActions.BOT_RELOAD,
        resource="bot",
        user_id=current_user.id,
        details={"cogs": cogs, "sync_commands": reload_data.sync_commands},
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "message": f"Reload request sent for: {', '.join(cogs)}",
        "reloaded_cogs": cogs,
    }


@router.get("/modules", response_model=ModuleListResponse)
@limit_api()
async def get_modules(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("module:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get all available modules.

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of modules
    """
    result = await db.execute(select(Module))
    modules = result.scalars().all()

    return {
        "modules": [ModuleResponse.model_validate(m) for m in modules],
        "total": len(modules),
    }


@router.get("/module/{module_name}", response_model=ModuleResponse)
@limit_api()
async def get_module(
    module_name: str,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("module:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Module:
    """Get a specific module.

    Args:
        module_name: Name of the module
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Module information
    """
    result = await db.execute(select(Module).where(Module.name == module_name))
    module = result.scalar_one_or_none()

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{module_name}' not found",
        )

    return module


@router.post("/module/enable", response_model=ModuleResponse)
@limit_api("10/minute")
async def enable_module(
    request: Request,
    toggle_data: ModuleToggle,
    current_user: Annotated[User, Depends(require_permission("module:enable"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Module:
    """Enable a module.

    Args:
        request: FastAPI request
        toggle_data: Module toggle data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated module
    """
    result = await db.execute(
        select(Module).where(Module.name == toggle_data.module_name)
    )
    module = result.scalar_one_or_none()

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{toggle_data.module_name}' not found",
        )

    module.is_enabled = True

    # Create audit log
    audit = AuditLog.create(
        action=AuditActions.MODULE_ENABLE,
        resource="module",
        resource_id=toggle_data.module_name,
        user_id=current_user.id,
        details={"guild_id": toggle_data.guild_id},
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(module)

    return module


@router.post("/module/disable", response_model=ModuleResponse)
@limit_api("10/minute")
async def disable_module(
    request: Request,
    toggle_data: ModuleToggle,
    current_user: Annotated[User, Depends(require_permission("module:disable"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Module:
    """Disable a module.

    Args:
        request: FastAPI request
        toggle_data: Module toggle data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated module
    """
    result = await db.execute(
        select(Module).where(Module.name == toggle_data.module_name)
    )
    module = result.scalar_one_or_none()

    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module '{toggle_data.module_name}' not found",
        )

    if module.is_core:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Core modules cannot be disabled",
        )

    module.is_enabled = False

    # Create audit log
    audit = AuditLog.create(
        action=AuditActions.MODULE_DISABLE,
        resource="module",
        resource_id=toggle_data.module_name,
        user_id=current_user.id,
        details={"guild_id": toggle_data.guild_id},
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(module)

    return module


@router.post("/log")
@limit_bot()
async def create_bot_log(
    request: Request,
    log_entry: BotLogEntry,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
) -> dict:
    """Create a bot log entry (called by bot).

    Args:
        request: FastAPI request
        log_entry: Log entry data
        db: Database session
        auth: Authentication tuple

    Returns:
        Success acknowledgment
    """
    user, api_key, is_bot_key = auth

    if not is_bot_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only bot can create log entries",
        )

    # In production, this would store to a log database or send to a log aggregator
    # For now, we just acknowledge receipt

    return {"status": "ok", "received": True}


@router.post("/audit")
@limit_bot()
async def create_bot_audit(
    request: Request,
    audit_entry: BotAuditEntry,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
) -> dict:
    """Create a bot audit log entry (called by bot).

    Args:
        request: FastAPI request
        audit_entry: Audit entry data
        db: Database session
        auth: Authentication tuple

    Returns:
        Success acknowledgment
    """
    user, api_key, is_bot_key = auth

    if not is_bot_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only bot can create audit entries",
        )

    audit = AuditLog.create(
        action=audit_entry.action,
        resource=audit_entry.resource,
        details=audit_entry.details,
        discord_user_id=audit_entry.user_id,
        discord_guild_id=audit_entry.guild_id,
    )
    db.add(audit)
    await db.commit()

    return {"status": "ok", "id": audit.id}
