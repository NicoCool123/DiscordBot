"""WebSocket connection manager."""

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState


class ConnectionManager:
    """Manages WebSocket connections for real-time communication."""

    def __init__(self):
        """Initialize the connection manager."""
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        channel: str = "default",
        user_id: Optional[int] = None,
    ) -> None:
        """Accept and register a WebSocket connection.

        Args:
            websocket: WebSocket connection
            channel: Channel to subscribe to
            user_id: Optional user ID for authentication
        """
        await websocket.accept()

        async with self._lock:
            if channel not in self._connections:
                self._connections[channel] = []
            self._connections[channel].append(websocket)

        # Send welcome message
        await self.send_personal(
            websocket,
            {
                "type": "connected",
                "channel": channel,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def disconnect(
        self,
        websocket: WebSocket,
        channel: str = "default",
    ) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: WebSocket connection
            channel: Channel to unsubscribe from
        """
        async with self._lock:
            if channel in self._connections:
                try:
                    self._connections[channel].remove(websocket)
                except ValueError:
                    pass

                if not self._connections[channel]:
                    del self._connections[channel]

    async def send_personal(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> bool:
        """Send a message to a specific connection.

        Args:
            websocket: WebSocket connection
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if websocket.application_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
                return True
        except Exception:
            pass
        return False

    async def broadcast(
        self,
        message: dict[str, Any],
        channel: str = "default",
    ) -> int:
        """Broadcast a message to all connections in a channel.

        Args:
            message: Message to broadcast
            channel: Channel to broadcast to

        Returns:
            Number of connections that received the message
        """
        sent = 0
        disconnected = []

        async with self._lock:
            connections = self._connections.get(channel, []).copy()

        for websocket in connections:
            try:
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                    sent += 1
                else:
                    disconnected.append(websocket)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected
        for websocket in disconnected:
            await self.disconnect(websocket, channel)

        return sent

    async def broadcast_all(self, message: dict[str, Any]) -> int:
        """Broadcast a message to all connections in all channels.

        Args:
            message: Message to broadcast

        Returns:
            Total number of connections that received the message
        """
        total = 0
        async with self._lock:
            channels = list(self._connections.keys())

        for channel in channels:
            total += await self.broadcast(message, channel)

        return total

    def get_connection_count(self, channel: Optional[str] = None) -> int:
        """Get the number of active connections.

        Args:
            channel: Optional channel to count (all if None)

        Returns:
            Number of connections
        """
        if channel:
            return len(self._connections.get(channel, []))
        return sum(len(conns) for conns in self._connections.values())

    def get_channels(self) -> list[str]:
        """Get list of active channels.

        Returns:
            List of channel names
        """
        return list(self._connections.keys())


# Global connection manager instance
manager = ConnectionManager()
