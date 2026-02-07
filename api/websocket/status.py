"""WebSocket endpoint for live status updates."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from api.core.config import settings
from api.core.jwt_handler import verify_token
from api.models import User
from api.websocket.manager import manager

router = APIRouter()


async def get_ws_user(websocket: WebSocket):
    token = websocket.query_params.get("token")
    api_key = websocket.query_params.get("api_key")

    # Bearer Token prüfen
    if token:
        payload = verify_token(token)
        if payload:
            return payload

    # API Key prüfen (z. B. vom Bot)
    if api_key == settings.bot_api_key:
        return {"bot": True}

    # Nicht authentifiziert
    return None
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
async def status_websocket(
    websocket: WebSocket,
    user = Depends(get_ws_user),
):
    if user is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, channel="status")

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
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await manager.send_personal(
                    websocket,
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                )

            elif data.get("type") == "status_update":
                await broadcast_status(data.get("data", {}))

    except WebSocketDisconnect:
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
