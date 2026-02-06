from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Annotated

from api.core.database import get_db
from api.core.rate_limiter import limit_api, limit_bot
from api.core.security import require_permission, get_current_user, get_api_key_or_user
from api.models.user import User
from api.models.audit_log import AuditLog, AuditActions
from api.models.module import Module
from api.schemas.bot import BotStatus, BotStatusUpdate, ModuleResponse, ModuleListResponse, ModuleToggle

router = APIRouter()

# In-memory bot status
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
    request: Request,  # <- unbedingt drin für slowapi
    current_user: Annotated[User, Depends(require_permission("bot:read"))],
):
    """Get bot status (requires authentication)"""
    return _bot_status


@router.post("/status")
@limit_bot()
async def update_bot_status(
    request: Request,  # <- unbedingt drin für slowapi
    status_update: BotStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[tuple, Depends(get_api_key_or_user)],  # gibt (user, api_key, is_bot_key) zurück
):
    """Update bot status (only bot/admin)"""
    user, api_key, is_bot_key = auth

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

# Module endpoints
@router.get("/modules", response_model=ModuleListResponse)
@limit_api()
async def get_modules(
    current_user: Annotated[User, Depends(require_permission("module:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Module))
    modules = result.scalars().all()
    return {"modules": [ModuleResponse.model_validate(m) for m in modules], "total": len(modules)}

@router.post("/module/enable", response_model=ModuleResponse)
@limit_api("10/minute")
async def enable_module(
    toggle_data: ModuleToggle,
    current_user: Annotated[User, Depends(require_permission("module:enable"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Module).where(Module.name == toggle_data.module_name))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Module '{toggle_data.module_name}' not found")
    module.is_enabled = True
    await db.commit()
    await db.refresh(module)
    return module

@router.post("/module/disable", response_model=ModuleResponse)
@limit_api("10/minute")
async def disable_module(
    toggle_data: ModuleToggle,
    current_user: Annotated[User, Depends(require_permission("module:disable"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Module).where(Module.name == toggle_data.module_name))
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Module '{toggle_data.module_name}' not found")
    if module.is_core:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Core modules cannot be disabled")
    module.is_enabled = False
    await db.commit()
    await db.refresh(module)
    return module