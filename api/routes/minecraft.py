"""Minecraft RCON API routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from mcrcon import MCRcon, MCRconException

from api.core.config import settings
from api.core.database import get_db
from api.core.rate_limiter import limit_rcon
from api.core.security import get_api_key_or_user, require_permission
from api.models.audit_log import AuditActions, AuditLog
from api.models.user import User
from api.schemas.minecraft import (
    MinecraftCommand,
    MinecraftCommandResponse,
    MinecraftStatus,
    MinecraftStatusReport,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

# Cached status
_minecraft_status: dict = {
    "online": False,
    "host": settings.rcon_host,
    "port": settings.rcon_port,
    "players_online": 0,
    "players_max": 0,
    "player_list": [],
    "tps": None,
    "version": None,
    "last_checked": datetime.utcnow(),
}

# Blocked commands for security
BLOCKED_COMMANDS = {"stop", "restart", "shutdown", "op", "deop", "ban-ip", "pardon-ip"}


def _execute_rcon(command: str) -> str:
    """Execute an RCON command.

    Args:
        command: Command to execute

    Returns:
        Command response

    Raises:
        MCRconException: If connection fails
    """
    with MCRcon(
        settings.rcon_host,
        settings.rcon_password,
        port=settings.rcon_port,
    ) as mcr:
        return mcr.command(command)


@router.get("/status", response_model=MinecraftStatus)
@limit_rcon()
async def get_minecraft_status(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("minecraft:read"))],
) -> dict:
    """Get Minecraft server status.

    Args:
        request: FastAPI request
        current_user: Current authenticated user

    Returns:
        Server status
    """
    if not settings.rcon_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Minecraft RCON is not enabled",
        )

    try:
        # Get player list
        list_response = _execute_rcon("list")

        # Parse response (format: "There are X of Y players online: player1, player2")
        players_online = 0
        players_max = 0
        player_list = []

        if "players online" in list_response.lower():
            parts = list_response.split(":")
            count_part = parts[0]

            # Extract numbers
            import re

            numbers = re.findall(r"\d+", count_part)
            if len(numbers) >= 2:
                players_online = int(numbers[0])
                players_max = int(numbers[1])

            # Extract player names
            if len(parts) > 1 and parts[1].strip():
                player_list = [p.strip() for p in parts[1].split(",") if p.strip()]

        # Update cached status
        global _minecraft_status
        _minecraft_status.update({
            "online": True,
            "players_online": players_online,
            "players_max": players_max,
            "player_list": player_list,
            "last_checked": datetime.utcnow(),
        })

        return _minecraft_status

    except MCRconException as e:
        _minecraft_status.update({
            "online": False,
            "last_checked": datetime.utcnow(),
        })
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to Minecraft server: {e}",
        )


@router.post("/command", response_model=MinecraftCommandResponse)
@limit_rcon("10/minute")
async def execute_minecraft_command(
    request: Request,
    command_data: MinecraftCommand,
    current_user: Annotated[User, Depends(require_permission("minecraft:command"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Execute a command on the Minecraft server.

    Args:
        request: FastAPI request
        command_data: Command to execute
        current_user: Current authenticated user
        db: Database session

    Returns:
        Command response
    """
    if not settings.rcon_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Minecraft RCON is not enabled",
        )

    command = command_data.command.strip()
    command_lower = command.lower()

    # Security check - block dangerous commands
    for blocked in BLOCKED_COMMANDS:
        if command_lower.startswith(blocked):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Command '{blocked}' is not allowed",
            )

    try:
        response = _execute_rcon(command)

        # Create audit log
        audit = AuditLog.create(
            action=AuditActions.MINECRAFT_COMMAND,
            resource="minecraft",
            user_id=current_user.id,
            details={
                "command": command,
                "response": response[:500],  # Truncate long responses
            },
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        await db.commit()

        return {
            "success": True,
            "command": command,
            "response": response,
            "executed_at": datetime.utcnow(),
        }

    except MCRconException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to execute command: {e}",
        )


@router.post("/status/report")
@limit_rcon()
async def report_minecraft_status(
    request: Request,
    status_report: MinecraftStatusReport,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[tuple, Depends(get_api_key_or_user)],
) -> dict:
    """Report Minecraft status from bot.

    Args:
        request: FastAPI request
        status_report: Status report data
        db: Database session
        auth: Authentication tuple

    Returns:
        Success acknowledgment
    """
    user, api_key, is_bot_key = auth

    if not is_bot_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only bot can report Minecraft status",
        )

    global _minecraft_status
    _minecraft_status.update({
        "online": status_report.online,
        "last_checked": datetime.utcnow(),
    })

    # Parse players from report
    if status_report.players:
        import re

        numbers = re.findall(r"\d+", status_report.players)
        if len(numbers) >= 2:
            _minecraft_status["players_online"] = int(numbers[0])
            _minecraft_status["players_max"] = int(numbers[1])

    return {"status": "ok"}


@router.post("/whitelist/{action}")
@limit_rcon("5/minute")
async def manage_whitelist(
    action: str,
    player: str,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("minecraft:command"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Add or remove a player from the whitelist.

    Args:
        action: "add" or "remove"
        player: Player name
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Operation result
    """
    if not settings.rcon_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Minecraft RCON is not enabled",
        )

    if action not in ("add", "remove"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'add' or 'remove'",
        )

    # Validate player name (alphanumeric and underscore only)
    if not player.replace("_", "").isalnum() or len(player) > 16:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid player name",
        )

    try:
        command = f"whitelist {action} {player}"
        response = _execute_rcon(command)

        # Create audit log
        audit = AuditLog.create(
            action=f"minecraft.whitelist_{action}",
            resource="minecraft",
            resource_id=player,
            user_id=current_user.id,
            details={"player": player, "response": response},
            ip_address=request.client.host if request.client else None,
        )
        db.add(audit)
        await db.commit()

        return {
            "success": True,
            "action": action,
            "player": player,
            "response": response,
        }

    except MCRconException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to modify whitelist: {e}",
        )
