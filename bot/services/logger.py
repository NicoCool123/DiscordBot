"""Structured logging service for the bot."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog
from structlog.types import Processor

from bot.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Common processors for all outputs
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.ExtraAdder(),
    ]

    if settings.log_format == "json":
        # JSON format for production
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable format for development
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging for third-party libraries
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=log_level,
        stream=sys.stdout,
    )

    # Set log levels for noisy libraries
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance with the given name."""
    return structlog.get_logger(name)


class BotLogger:
    """Bot logger with WebSocket broadcast support."""

    def __init__(self, name: str = "bot"):
        """Initialize the bot logger."""
        self.logger = get_logger(name)
        self._log_buffer: list[dict[str, Any]] = []
        self._max_buffer_size: int = 1000
        self._websocket_callback: Optional[callable] = None

    def set_websocket_callback(self, callback: callable) -> None:
        """Set callback for broadcasting logs via WebSocket."""
        self._websocket_callback = callback

    async def _broadcast_log(self, log_entry: dict[str, Any]) -> None:
        """Broadcast log entry via WebSocket if callback is set."""
        if self._websocket_callback:
            try:
                await self._websocket_callback(log_entry)
            except Exception:
                pass  # Don't let WebSocket errors affect logging

    def _add_to_buffer(self, log_entry: dict[str, Any]) -> None:
        """Add log entry to buffer for retrieval."""
        self._log_buffer.append(log_entry)
        if len(self._log_buffer) > self._max_buffer_size:
            self._log_buffer.pop(0)

    def _create_log_entry(
        self,
        level: str,
        message: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a structured log entry."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "extra": kwargs,
        }

    async def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(message, **kwargs)
        entry = self._create_log_entry("DEBUG", message, **kwargs)
        self._add_to_buffer(entry)
        await self._broadcast_log(entry)

    async def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)
        entry = self._create_log_entry("INFO", message, **kwargs)
        self._add_to_buffer(entry)
        await self._broadcast_log(entry)

    async def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)
        entry = self._create_log_entry("WARNING", message, **kwargs)
        self._add_to_buffer(entry)
        await self._broadcast_log(entry)

    async def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(message, **kwargs)
        entry = self._create_log_entry("ERROR", message, **kwargs)
        self._add_to_buffer(entry)
        await self._broadcast_log(entry)

    async def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self.logger.critical(message, **kwargs)
        entry = self._create_log_entry("CRITICAL", message, **kwargs)
        self._add_to_buffer(entry)
        await self._broadcast_log(entry)

    def get_recent_logs(self, count: int = 100) -> list[dict[str, Any]]:
        """Get recent log entries from buffer."""
        return self._log_buffer[-count:]

    def clear_buffer(self) -> None:
        """Clear the log buffer."""
        self._log_buffer.clear()


# Global bot logger instance
bot_logger = BotLogger()
