"""Dashboard API routes."""

import os
import platform
import sys
from datetime import datetime, timedelta
from typing import Annotated

import psutil
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.rate_limiter import limit_api
from api.core.security import require_permission
from api.models.audit_log import AuditLog
from api.models.bot_settings import BotSettings
from api.models.user import User

router = APIRouter()


@router.get("/metrics")
@limit_api()
async def get_dashboard_metrics(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("dashboard:metrics"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get dashboard metrics and statistics.

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dashboard metrics
    """
    # Get user count
    user_count_result = await db.execute(select(func.count(User.id)))
    user_count = user_count_result.scalar() or 0

    # Get active user count (last 24h)
    day_ago = datetime.utcnow() - timedelta(days=1)
    active_users_result = await db.execute(
        select(func.count(User.id)).where(User.last_login >= day_ago)
    )
    active_users = active_users_result.scalar() or 0

    # Get guild count
    guild_count_result = await db.execute(select(func.count(BotSettings.id)))
    guild_count = guild_count_result.scalar() or 0

    # Get recent audit log count
    audit_count_result = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.created_at >= day_ago)
    )
    audit_count = audit_count_result.scalar() or 0

    # System metrics
    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "users": {
            "total": user_count,
            "active_24h": active_users,
        },
        "guilds": {
            "total": guild_count,
        },
        "audit": {
            "events_24h": audit_count,
        },
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_used_mb": memory_info.rss / 1024 / 1024,
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage(os.path.abspath(os.sep)).percent,
            "python_version": sys.version.split()[0],
            "platform": platform.system(),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/logs")
@limit_api()
async def get_audit_logs(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("audit:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    action: str = Query(None, description="Filter by action"),
    resource: str = Query(None, description="Filter by resource"),
) -> dict:
    """Get paginated audit logs.

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session
        page: Page number
        per_page: Items per page
        action: Optional action filter
        resource: Optional resource filter

    Returns:
        Paginated audit logs
    """
    # Build query
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
    if resource:
        query = query.where(AuditLog.resource == resource)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    offset = (page - 1) * per_page
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "user_id": log.user_id,
                "discord_user_id": log.discord_user_id,
                "discord_guild_id": log.discord_guild_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/activity")
@limit_api()
async def get_recent_activity(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("dashboard:view"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """Get recent activity feed.

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session
        limit: Number of items to return

    Returns:
        Recent activity items
    """
    # Get recent audit logs
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    activity = []
    for log in logs:
        activity.append({
            "id": log.id,
            "type": log.action,
            "resource": log.resource,
            "description": _format_activity_description(log),
            "timestamp": log.created_at.isoformat(),
        })

    return {
        "activity": activity,
        "count": len(activity),
    }


def _format_activity_description(log: AuditLog) -> str:
    """Format an audit log entry into a human-readable description."""
    action_descriptions = {
        "auth.login": "User logged in",
        "auth.logout": "User logged out",
        "auth.login_failed": "Failed login attempt",
        "auth.password_change": "Password changed",
        "auth.mfa_enable": "MFA enabled",
        "auth.mfa_disable": "MFA disabled",
        "user.create": "User account created",
        "user.update": "User profile updated",
        "user.delete": "User account deleted",
        "bot.reload": "Bot reloaded",
        "bot.settings_update": "Bot settings updated",
        "module.enable": f"Module '{log.resource_id}' enabled",
        "module.disable": f"Module '{log.resource_id}' disabled",
        "minecraft.command": "Minecraft command executed",
        "api_key.create": "API key created",
        "api_key.revoke": "API key revoked",
    }

    return action_descriptions.get(log.action, f"{log.action} on {log.resource}")


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for monitoring.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
