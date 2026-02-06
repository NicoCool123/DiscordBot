"""WebSocket endpoint for live status updates."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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

    # Check for API key (for bot)
    api_key = websocket.query_params.get("api_key")
    if api_key == settings.bot_api_key:
        return True

    return False


@router.websocket("/status")
async def status_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for live status updates.

    Args:
        websocket: WebSocket connection
    """
    # Authenticate
    if not await authenticate_websocket(websocket):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Connect to status channel
    await manager.connect(websocket, channel="status")

    # Send initial message
    await manager.send_personal(
        websocket,
        {
            "type": "subscribed",
            "channel": "status",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await manager.send_personal(
                    websocket,
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                )

            elif data.get("type") == "status_update":
                # Bot is sending status update
                await broadcast_status(data.get("data", {}))

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await manager.disconnect(websocket, channel="status")


async def broadcast_status(status_data: dict[str, Any]) -> int:
    """Broadcast status update to all connected clients.

    Args:
        status_data: Status data to broadcast

    Returns:
        Number of clients that received the status
    """
    message = {
        "type": "status",
        "data": status_data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return await manager.broadcast(message, channel="status")


async def broadcast_bot_event(event_type: str, event_data: dict[str, Any]) -> int:
    """Broadcast a bot event to all connected clients.

    Args:
        event_type: Type of event (e.g., "guild_join", "command_used")
        event_data: Event data

    Returns:
        Number of clients that received the event
    """
    message = {
        "type": "event",
        "event_type": event_type,
        "data": event_data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return await manager.broadcast(message, channel="status")
