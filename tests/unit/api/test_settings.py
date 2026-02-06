"""Tests for bot settings API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.bot_settings import BotSettings


class TestGuildSettings:
    """Tests for guild settings CRUD."""

    async def test_create_guild_settings(
        self, client: AsyncClient, bot_headers
    ):
        response = await client.post(
            "/api/v1/settings",
            headers=bot_headers,
            json={
                "guild_id": "111222333444",
                "prefix": "!",
                "language": "en",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["guild_id"] == "111222333444"
        assert data["prefix"] == "!"

    async def test_get_guild_settings(
        self, client: AsyncClient, bot_headers, db_session: AsyncSession
    ):
        # Create settings first
        settings = BotSettings(guild_id="222333444555", prefix="?", language="de")
        db_session.add(settings)
        await db_session.commit()

        response = await client.get(
            "/api/v1/settings/222333444555", headers=bot_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["guild_id"] == "222333444555"
        assert data["prefix"] == "?"

    async def test_get_settings_not_found(
        self, client: AsyncClient, bot_headers
    ):
        response = await client.get(
            "/api/v1/settings/999999999999", headers=bot_headers
        )
        assert response.status_code == 404

    async def test_update_guild_settings(
        self, client: AsyncClient, bot_headers, db_session: AsyncSession
    ):
        # Create settings first
        settings = BotSettings(guild_id="333444555666", prefix="!", language="en")
        db_session.add(settings)
        await db_session.commit()

        response = await client.put(
            "/api/v1/settings/333444555666",
            headers=bot_headers,
            json={"prefix": ">>", "language": "de"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["prefix"] == ">>"
        assert data["language"] == "de"

    async def test_delete_guild_settings(
        self, client: AsyncClient, test_admin, admin_headers, db_session: AsyncSession
    ):
        # Create settings first
        settings = BotSettings(guild_id="444555666777", prefix="!", language="en")
        db_session.add(settings)
        await db_session.commit()

        response = await client.delete(
            "/api/v1/settings/444555666777", headers=admin_headers
        )
        assert response.status_code == 200
