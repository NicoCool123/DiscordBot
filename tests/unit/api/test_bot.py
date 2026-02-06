"""Tests for bot management API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.module import Module


class TestBotStatus:
    """Tests for bot status endpoints."""

    async def test_get_bot_status(
        self, client: AsyncClient, test_admin, admin_headers
    ):
        response = await client.get("/api/v1/bot/status", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "online" in data
        assert "guild_count" in data
        assert "latency_ms" in data

    async def test_get_bot_status_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/bot/status")
        assert response.status_code == 401

    async def test_update_bot_status(self, client: AsyncClient, bot_headers):
        response = await client.post(
            "/api/v1/bot/status",
            headers=bot_headers,
            json={
                "guild_count": 5,
                "user_count": 100,
                "latency_ms": 42.5,
                "uptime_seconds": 3600.0,
            },
        )
        assert response.status_code == 200


class TestModules:
    """Tests for module management endpoints."""

    async def test_get_modules(
        self, client: AsyncClient, test_admin, admin_headers, db_session: AsyncSession
    ):
        # Create a test module
        module = Module(
            name="test_module",
            display_name="Test Module",
            description="A test module",
            category="test",
            is_enabled=True,
            is_core=False,
        )
        db_session.add(module)
        await db_session.commit()

        response = await client.get("/api/v1/bot/modules", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "modules" in data
        assert data["total"] >= 1

    async def test_get_module_not_found(
        self, client: AsyncClient, test_admin, admin_headers
    ):
        response = await client.get(
            "/api/v1/bot/module/nonexistent", headers=admin_headers
        )
        assert response.status_code == 404

    async def test_disable_core_module(
        self, client: AsyncClient, test_admin, admin_headers, db_session: AsyncSession
    ):
        # Create a core module
        module = Module(
            name="core_test",
            display_name="Core Test",
            description="A core module",
            category="core",
            is_enabled=True,
            is_core=True,
        )
        db_session.add(module)
        await db_session.commit()

        response = await client.post(
            "/api/v1/bot/module/disable",
            headers=admin_headers,
            json={"module_name": "core_test"},
        )
        assert response.status_code == 400
        assert "Core modules cannot be disabled" in response.json()["detail"]
