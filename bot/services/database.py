"""Database service for direct bot database access."""

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.services.logger import get_logger

logger = get_logger(__name__)


class DatabaseService:
    """Async database service for the bot."""

    def __init__(self, database_url: str):
        """Initialize the database service.

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self._engine = None
        self._session_factory = None

    async def connect(self) -> None:
        """Create database connection pool."""
        try:
            self._engine = create_async_engine(
                self.database_url,
                echo=False,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connection closed")

    async def get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._session_factory()

    async def execute(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Execute a raw SQL query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of result rows as dictionaries
        """
        async with await self.get_session() as session:
            result = await session.execute(text(query), params or {})
            await session.commit()

            if result.returns_rows:
                rows = result.fetchall()
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
            return []

    # -------------------------------------------------------------------------
    # Guild Settings Helpers
    # -------------------------------------------------------------------------

    async def get_guild_prefix(self, guild_id: int) -> Optional[str]:
        """Get the command prefix for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            Command prefix or None if not found
        """
        try:
            result = await self.execute(
                "SELECT prefix FROM bot_settings WHERE guild_id = :guild_id",
                {"guild_id": str(guild_id)},
            )
            if result:
                return result[0]["prefix"]
            return None
        except Exception as e:
            logger.error(f"Failed to get prefix for guild {guild_id}: {e}")
            return None

    async def set_guild_prefix(self, guild_id: int, prefix: str) -> bool:
        """Set the command prefix for a guild.

        Args:
            guild_id: Discord guild ID
            prefix: New command prefix

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.execute(
                """
                INSERT INTO bot_settings (guild_id, prefix, updated_at)
                VALUES (:guild_id, :prefix, NOW())
                ON CONFLICT (guild_id)
                DO UPDATE SET prefix = :prefix, updated_at = NOW()
                """,
                {"guild_id": str(guild_id), "prefix": prefix},
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set prefix for guild {guild_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # Module State Helpers
    # -------------------------------------------------------------------------

    async def is_module_enabled(
        self, module_name: str, guild_id: Optional[int] = None
    ) -> bool:
        """Check if a module is enabled.

        Args:
            module_name: Name of the module
            guild_id: Optional guild ID for guild-specific check

        Returns:
            True if enabled, False otherwise
        """
        try:
            if guild_id:
                result = await self.execute(
                    """
                    SELECT is_enabled FROM modules
                    WHERE name = :name AND guild_id = :guild_id
                    """,
                    {"name": module_name, "guild_id": str(guild_id)},
                )
            else:
                result = await self.execute(
                    "SELECT is_enabled FROM modules WHERE name = :name AND guild_id IS NULL",
                    {"name": module_name},
                )

            if result:
                return result[0]["is_enabled"]
            return True  # Default to enabled if not found
        except Exception as e:
            logger.error(f"Failed to check module status for {module_name}: {e}")
            return True

    # -------------------------------------------------------------------------
    # Audit Log Helpers
    # -------------------------------------------------------------------------

    async def create_audit_log(
        self,
        action: str,
        resource: str,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> bool:
        """Create an audit log entry directly in the database.

        Args:
            action: Action performed
            resource: Resource affected
            user_id: Discord user ID
            guild_id: Discord guild ID
            details: Additional details as JSON

        Returns:
            True if successful, False otherwise
        """
        import json

        try:
            await self.execute(
                """
                INSERT INTO audit_logs (action, resource, user_id, guild_id, details, created_at)
                VALUES (:action, :resource, :user_id, :guild_id, :details, NOW())
                """,
                {
                    "action": action,
                    "resource": resource,
                    "user_id": str(user_id) if user_id else None,
                    "guild_id": str(guild_id) if guild_id else None,
                    "details": json.dumps(details or {}),
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            return False

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Check if database is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            await self.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
