"""WebSocket endpoint for live logs."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jwt.exceptions import PyJWTError

from api.core.config import settings
from api.core.jwt_handler import verify_token
from api.websocket.manager import manager

router = APIRouter()


async def authenticate_websocket(websocket: WebSocket) -> bool:
    """Authenticate a WebSocket connection.

    Args:
        websocket: WebSocket connection

    Returns:
        True if authenticated, False otherwise
    """
    # Check for token in query params
    token = websocket.query_params.get("token")
    if token:
        payload = verify_token(token)
        if payload:
            return True

    # Check for API key
    api_key = websocket.query_params.get("api_key")
    if api_key == settings.bot_api_key:
        return True

    return False


@router.websocket("/logs")
async def logs_websocket(
    websocket: WebSocket,
    level: str = Query("INFO", description="Minimum log level"),
) -> None:
    """WebSocket endpoint for live log streaming.

    Args:
        websocket: WebSocket connection
        level: Minimum log level to receive
    """
    # Authenticate
    if not await authenticate_websocket(websocket):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Connect to logs channel
    await manager.connect(websocket, channel="logs")

    # Send initial message
    await manager.send_personal(
        websocket,
        {
            "type": "subscribed",
            "channel": "logs",
            "level": level,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    try:
        while True:
            # Wait for messages from client (ping/pong, filter changes)
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await manager.send_personal(
                    websocket,
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                )

            elif data.get("type") == "set_level":
                level = data.get("level", "INFO")
                await manager.send_personal(
                    websocket,
                    {
                        "type": "level_changed",
                        "level": level,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket, channel="logs")


async def broadcast_log(log_entry: dict[str, Any]) -> int:
    """Broadcast a log entry to all connected clients.

    Args:
        log_entry: Log entry to broadcast

    Returns:
        Number of clients that received the log
    """
    message = {
        "type": "log",
        "data": log_entry,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return await manager.broadcast(message, channel="logs")
