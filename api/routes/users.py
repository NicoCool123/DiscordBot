"""User management API routes."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.rate_limiter import limit_api
from api.core.security import get_current_active_user, require_permission
from api.models.api_key import APIKey
from api.models.audit_log import AuditLog, AuditActions
from api.models.role import Role, UserRole
from api.models.user import User

router = APIRouter()


# --- Schemas ---

class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role_ids: Optional[list[int]] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    permissions: list[str] = []

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    roles: list[RoleResponse] = []
    last_login: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


# --- Routes ---

@router.get("/")
@limit_api()
async def list_users(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("user:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
) -> dict:
    """List all users with pagination."""
    query = select(User)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            User.username.ilike(pattern)
            | User.email.ilike(pattern)
            | User.display_name.ilike(pattern)
        )

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginated results
    offset = (page - 1) * per_page
    query = query.order_by(User.id).offset(offset).limit(per_page)
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "display_name": u.display_name,
                "is_active": u.is_active,
                "is_superuser": u.is_superuser,
                "roles": [{"id": r.id, "name": r.name} for r in u.roles],
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


@router.get("/roles")
@limit_api()
async def list_roles(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("user:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """List all available roles."""
    result = await db.execute(select(Role).order_by(Role.name))
    roles = result.scalars().all()

    return {
        "roles": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "permissions": r.permissions or [],
            }
            for r in roles
        ]
    }


@router.get("/{user_id}")
@limit_api()
async def get_user(
    request: Request,
    user_id: int,
    current_user: Annotated[User, Depends(require_permission("user:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get a single user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "is_verified": user.is_verified,
        "mfa_enabled": user.mfa_enabled,
        "discord_id": user.discord_id,
        "roles": [{"id": r.id, "name": r.name} for r in user.roles],
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat(),
    }


@router.patch("/{user_id}")
@limit_api()
async def update_user(
    request: Request,
    user_id: int,
    data: AdminUserUpdate,
    current_user: Annotated[User, Depends(require_permission("user:write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Update a user (admin action)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent non-superusers from modifying superusers
    if user.is_superuser and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot modify a superuser")

    # Prevent non-superusers from granting superuser
    if data.is_superuser is not None and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can grant superuser status")

    changes = {}

    if data.display_name is not None:
        user.display_name = data.display_name
        changes["display_name"] = data.display_name

    if data.email is not None:
        # Check uniqueness
        existing = await db.execute(
            select(User).where(User.email == data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email
        changes["email"] = data.email

    if data.is_active is not None:
        user.is_active = data.is_active
        changes["is_active"] = data.is_active

    if data.is_superuser is not None:
        user.is_superuser = data.is_superuser
        changes["is_superuser"] = data.is_superuser

    if data.role_ids is not None:
        # Remove existing roles
        await db.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        from sqlalchemy import delete
        await db.execute(
            delete(UserRole).where(UserRole.user_id == user_id)
        )
        # Add new roles
        for role_id in data.role_ids:
            role_check = await db.execute(select(Role).where(Role.id == role_id))
            if role_check.scalar_one_or_none():
                db.add(UserRole(user_id=user_id, role_id=role_id))
        changes["role_ids"] = data.role_ids

    # Audit log
    AuditLog.create_and_add(
        db,
        action=AuditActions.USER_UPDATE,
        resource="user",
        user_id=current_user.id,
        resource_id=str(user_id),
        details=changes,
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    # Refresh to get updated roles
    await db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "roles": [{"id": r.id, "name": r.name} for r in user.roles],
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat(),
    }


@router.delete("/{user_id}")
@limit_api()
async def delete_user(
    request: Request,
    user_id: int,
    current_user: Annotated[User, Depends(require_permission("user:delete"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a user (admin action)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_superuser and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot delete a superuser")

    username = user.username

    # Audit log before delete
    AuditLog.create_and_add(
        db,
        action=AuditActions.USER_DELETE,
        resource="user",
        user_id=current_user.id,
        resource_id=str(user_id),
        details={"username": username},
        ip_address=request.client.host if request.client else None,
    )

    await db.delete(user)
    await db.commit()

    return {"detail": f"User '{username}' deleted"}


@router.get("/me/export")
@limit_api()
async def export_user_data(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Export all user data (GDPR compliance - Article 15).

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dict containing all user data
    """
    # Get audit logs
    result = await db.execute(
        select(AuditLog).where(AuditLog.user_id == current_user.id).order_by(AuditLog.created_at.desc())
    )
    audit_logs = result.scalars().all()

    # Get API keys
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc())
    )
    api_keys = result.scalars().all()

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "display_name": current_user.display_name,
            "discord_id": current_user.discord_id,
            "mfa_enabled": current_user.mfa_enabled,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "is_verified": current_user.is_verified,
            "created_at": current_user.created_at.isoformat(),
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        },
        "roles": [
            {
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": role.permissions or [],
            }
            for role in current_user.roles
        ],
        "audit_logs": [
            {
                "action": log.action,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "created_at": log.created_at.isoformat(),
                "details": log.details,
            }
            for log in audit_logs
        ],
        "api_keys": [
            {
                "name": key.name,
                "description": key.description,
                "created_at": key.created_at.isoformat(),
                "is_active": key.is_active,
            }
            for key in api_keys
        ],
    }


@router.delete("/me")
@limit_api()
async def delete_user_account(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    confirmation: str = Query(..., description="Must be 'DELETE MY ACCOUNT'"),
) -> dict:
    """Delete user account and all associated data (GDPR right to erasure - Article 17).

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session
        confirmation: Confirmation string (must be "DELETE MY ACCOUNT")

    Returns:
        Success message

    Raises:
        HTTPException: If confirmation is incorrect
    """
    if confirmation != "DELETE MY ACCOUNT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required: 'DELETE MY ACCOUNT'",
        )

    username = current_user.username

    # Create final audit log
    AuditLog.create_and_add(
        db,
        action=AuditActions.USER_DELETE,
        resource="user",
        user_id=current_user.id,
        resource_id=str(current_user.id),
        details={"username": username, "self_deletion": True},
        ip_address=request.client.host if request.client else None,
    )

    # Delete audit logs
    await db.execute(delete(AuditLog).where(AuditLog.user_id == current_user.id))

    # Delete API keys
    await db.execute(delete(APIKey).where(APIKey.user_id == current_user.id))

    # Delete user roles
    await db.execute(delete(UserRole).where(UserRole.user_id == current_user.id))

    # Delete user
    await db.delete(current_user)
    await db.commit()

    return {"message": f"Account '{username}' deleted successfully"}
