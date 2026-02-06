"""Tests for the bot API connector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.services.api_connector import APIConnector, APIError


class TestAPIConnector:
    """Tests for APIConnector class."""

    def test_init(self):
        connector = APIConnector("http://localhost:8000", "test-key")
        assert connector.base_url == "http://localhost:8000"
        assert connector.api_key == "test-key"

    def test_init_strips_trailing_slash(self):
        connector = APIConnector("http://localhost:8000/", "test-key")
        assert connector.base_url == "http://localhost:8000"

    async def test_close_no_session(self):
        connector = APIConnector("http://localhost:8000", "test-key")
        # Should not raise when no session exists
        await connector.close()

    async def test_close_with_session(self):
        connector = APIConnector("http://localhost:8000", "test-key")
        mock_session = AsyncMock()
        mock_session.closed = False
        connector._session = mock_session
        await connector.close()
        mock_session.close.assert_called_once()

    def test_session_creates_on_access(self):
        connector = APIConnector("http://localhost:8000", "test-key")
        session = connector.session
        assert session is not None
        # Clean up
        assert not session.closed


class TestAPIError:
    """Tests for APIError exception."""

    def test_api_error(self):
        error = APIError(404, "Not Found")
        assert error.status_code == 404
        assert error.message == "Not Found"
        assert "404" in str(error)

    def test_api_error_str(self):
        error = APIError(500, "Server Error")
        assert str(error) == "API Error 500: Server Error"
