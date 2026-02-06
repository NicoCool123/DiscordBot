"""API Connector for bot-backend communication."""

from typing import Any, Optional

import aiohttp

from bot.services.logger import get_logger

logger = get_logger(__name__)


class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class APIConnector:

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "DiscordBot/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session
    """Handles secure communication between bot and backend API."""

    def __init__(self, base_url: str, api_key: str):
        """Initialize the API connector.

        Args:
            base_url: Base URL of the backend API
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "DiscordBot/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("API connector session closed")

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for aiohttp request

        Returns:
            JSON response as dictionary

        Raises:
            APIError: If the request fails
        """
        url = f"{self.base_url}/api/v1{endpoint}"

        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status >= 400:
                    error_body = await response.text()
                    logger.error(
                        f"API request failed",
                        method=method,
                        url=url,
                        status=response.status,
                        error=error_body,
                    )
                    raise APIError(response.status, error_body)

                if response.content_type == "application/json":
                    return await response.json()
                return {"status": "ok"}

        except aiohttp.ClientError as e:
            logger.error(f"API connection error", method=method, url=url, error=str(e))
            raise APIError(503, f"Connection error: {e}")

    async def get(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make a GET request."""
        return await self._request("GET", endpoint, **kwargs)

    async def post(
        self, endpoint: str, data: Optional[dict] = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Make a POST request."""
        return await self._request("POST", endpoint, json=data, **kwargs)

    async def put(
        self, endpoint: str, data: Optional[dict] = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Make a PUT request."""
        return await self._request("PUT", endpoint, json=data, **kwargs)

    async def delete(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        """Make a DELETE request."""
        return await self._request("DELETE", endpoint, **kwargs)

    # -------------------------------------------------------------------------
    # Bot Settings API
    # -------------------------------------------------------------------------

    async def get_guild_settings(self, guild_id: int) -> dict[str, Any]:
        """Get settings for a specific guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            Guild settings dictionary
        """
        return await self.get(f"/bot/settings/{guild_id}")

    async def create_guild_settings(
        self,
        guild_id: int,
        prefix: str = "!",
        language: str = "en",
        **extra_settings: Any,
    ) -> dict[str, Any]:
        """Create settings for a new guild.

        Args:
            guild_id: Discord guild ID
            prefix: Command prefix
            language: Bot language
            **extra_settings: Additional settings

        Returns:
            Created settings dictionary
        """
        return await self.post(
            "/bot/settings",
            data={
                "guild_id": str(guild_id),
                "prefix": prefix,
                "language": language,
                "settings": extra_settings,
            },
        )

    async def update_guild_settings(
        self,
        guild_id: int,
        **settings: Any,
    ) -> dict[str, Any]:
        """Update settings for a guild.

        Args:
            guild_id: Discord guild ID
            **settings: Settings to update

        Returns:
            Updated settings dictionary
        """
        return await self.put(f"/bot/settings/{guild_id}", data=settings)

    # -------------------------------------------------------------------------
    # Module API
    # -------------------------------------------------------------------------

    async def get_modules(self) -> list[dict[str, Any]]:
        """Get all available modules."""
        return await self.get("/bot/modules")

    async def get_module_status(self, module_name: str) -> dict[str, Any]:
        """Get status of a specific module."""
        return await self.get(f"/bot/module/{module_name}")

    async def enable_module(
        self, module_name: str, guild_id: Optional[int] = None
    ) -> dict[str, Any]:
        """Enable a module.

        Args:
            module_name: Name of the module
            guild_id: Optional guild ID for guild-specific enable

        Returns:
            Module status dictionary
        """
        data = {"module_name": module_name}
        if guild_id:
            data["guild_id"] = str(guild_id)
        return await self.post("/bot/module/enable", data=data)

    async def disable_module(
        self, module_name: str, guild_id: Optional[int] = None
    ) -> dict[str, Any]:
        """Disable a module.

        Args:
            module_name: Name of the module
            guild_id: Optional guild ID for guild-specific disable

        Returns:
            Module status dictionary
        """
        data = {"module_name": module_name}
        if guild_id:
            data["guild_id"] = str(guild_id)
        return await self.post("/bot/module/disable", data=data)

    # -------------------------------------------------------------------------
    # Status & Metrics API
    # -------------------------------------------------------------------------

    async def report_status(
        self,
        guild_count: int,
        user_count: int,
        latency_ms: float,
        uptime_seconds: float,
    ) -> dict[str, Any]:
        """Report bot status to the API.

        Args:
            guild_count: Number of connected guilds
            user_count: Total user count
            latency_ms: WebSocket latency in milliseconds
            uptime_seconds: Bot uptime in seconds

        Returns:
            Status acknowledgment
        """
        return await self.post(
            "/bot/status",
            data={
                "guild_count": guild_count,
                "user_count": user_count,
                "latency_ms": latency_ms,
                "uptime_seconds": uptime_seconds,
            },
        )

    async def send_log(
        self,
        level: str,
        message: str,
        extra: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Send a log entry to the API.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            extra: Additional log data

        Returns:
            Log acknowledgment
        """
        return await self.post(
            "/bot/log",
            data={
                "level": level,
                "message": message,
                "extra": extra or {},
            },
        )

    # -------------------------------------------------------------------------
    # Minecraft API
    # -------------------------------------------------------------------------

    async def get_minecraft_status(self) -> dict[str, Any]:
        """Get Minecraft server status."""
        return await self.get("/minecraft/status")

    async def send_minecraft_command(self, command: str) -> dict[str, Any]:
        """Send a command to the Minecraft server.

        Args:
            command: RCON command to execute

        Returns:
            Command response
        """
        return await self.post("/minecraft/command", data={"command": command})

    # -------------------------------------------------------------------------
    # Audit Log API
    # -------------------------------------------------------------------------

    async def create_audit_log(
        self,
        action: str,
        resource: str,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Create an audit log entry.

        Args:
            action: Action performed
            resource: Resource affected
            user_id: Discord user ID
            guild_id: Discord guild ID
            details: Additional details

        Returns:
            Created audit log entry
        """
        return await self.post(
            "/bot/audit",
            data={
                "action": action,
                "resource": resource,
                "user_id": str(user_id) if user_id else None,
                "guild_id": str(guild_id) if guild_id else None,
                "details": details or {},
            },
        )
