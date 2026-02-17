"""Audit log management API routes."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.rate_limiter import limit_api
from api.core.security import require_permission
from api.models.audit_log import AuditLog
from api.models.user import User

router = APIRouter()


@router.post("/cleanup", status_code=status.HTTP_200_OK)
@limit_api("5/minute")
async def cleanup_old_audit_logs(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("audit:admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 90,
) -> dict:
    """Delete audit logs older than retention period.

    Args:
        request: FastAPI request
        current_user: Current authenticated user with audit:admin permission
        db: Database session
        days: Number of days to keep (default 90)

    Returns:
        Dict with deleted count and message
    """
    # Delete logs older than retention period
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        delete(AuditLog).where(AuditLog.created_at < cutoff)
    )
    await db.commit()

    return {
        "deleted": result.rowcount,
        "message": f"Deleted {result.rowcount} audit logs older than {days} days",
    }


@router.post("/anonymize", status_code=status.HTTP_200_OK)
@limit_api("5/minute")
async def anonymize_old_audit_logs(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("audit:admin"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
) -> dict:
    """Anonymize IP addresses and user agents in old audit logs.

    Args:
        request: FastAPI request
        current_user: Current authenticated user with audit:admin permission
        db: Database session
        days: Anonymize logs older than this many days (default 30)

    Returns:
        Dict with anonymized count and message
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        update(AuditLog)
        .where(
            AuditLog.created_at < cutoff,
            AuditLog.anonymized == False,  # noqa: E712
        )
        .values(
            ip_address="0.0.0.0",
            user_agent="[ANONYMIZED]",
            anonymized=True,
        )
    )
    await db.commit()

    return {
        "anonymized": result.rowcount,
        "message": f"Anonymized {result.rowcount} audit logs older than {days} days",
    }
