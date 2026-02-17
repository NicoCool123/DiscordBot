"""API Routes Package."""

from fastapi import APIRouter
from .audit import router as audit_router
from .auth import router as auth_router
from .bot import router as bot_router
from .settings import router as settings_router
from .dashboard import router as dashboard_router
from .minecraft import router as minecraft_router
from .guilds import router as guilds_router
from .commands import router as commands_router
from .users import router as users_router

api_router = APIRouter()

api_router.include_router(audit_router, prefix="/audit", tags=["Audit"])
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(bot_router, prefix="/bot", tags=["Bot Management"])
api_router.include_router(settings_router, prefix="/settings", tags=["Settings"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(minecraft_router, prefix="/minecraft", tags=["Minecraft"])
api_router.include_router(guilds_router, prefix="/guilds", tags=["Guilds"])
api_router.include_router(commands_router, prefix="/commands", tags=["Commands"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])

__all__ = ["api_router"]
