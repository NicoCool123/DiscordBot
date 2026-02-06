"""Integration tests for the full API flow."""

import pytest
from httpx import AsyncClient


class TestAuthFlow:
    """Test complete authentication flow: register -> login -> use token -> refresh."""

    async def test_full_auth_flow(self, client: AsyncClient):
        # 1. Register a new user
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "flowuser",
                "email": "flow@example.com",
                "password": "FlowPassword123",
            },
        )
        assert register_response.status_code == 201
        user_data = register_response.json()
        assert user_data["username"] == "flowuser"

        # 2. Login with the new user
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "flowuser", "password": "FlowPassword123"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # 3. Access protected endpoint
        me_response = await client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "flowuser"

        # 4. Update profile
        update_response = await client.patch(
            "/api/v1/auth/me",
            headers=headers,
            json={"display_name": "Flow User"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["display_name"] == "Flow User"

        # 5. Refresh token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens

        # 6. Use new token
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        me_response2 = await client.get("/api/v1/auth/me", headers=new_headers)
        assert me_response2.status_code == 200
        assert me_response2.json()["display_name"] == "Flow User"

        # 7. Logout
        logout_response = await client.post(
            "/api/v1/auth/logout", headers=new_headers
        )
        assert logout_response.status_code == 200

    async def test_login_with_email(self, client: AsyncClient):
        # Register
        await client.post(
            "/api/v1/auth/register",
            json={
                "username": "emailuser",
                "email": "emaillogin@example.com",
                "password": "EmailPassword123",
            },
        )

        # Login using email
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "emaillogin@example.com", "password": "EmailPassword123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestSettingsFlow:
    """Test complete settings flow: create -> read -> update -> delete."""

    async def test_full_settings_flow(
        self, client: AsyncClient, test_admin, admin_headers, bot_headers
    ):
        guild_id = "555666777888"

        # 1. Create guild settings (via bot)
        create_response = await client.post(
            "/api/v1/settings",
            headers=bot_headers,
            json={
                "guild_id": guild_id,
                "prefix": "!",
                "language": "en",
                "moderation_enabled": True,
            },
        )
        assert create_response.status_code == 201
        settings = create_response.json()
        assert settings["guild_id"] == guild_id
        assert settings["prefix"] == "!"

        # 2. Read settings (via bot)
        get_response = await client.get(
            f"/api/v1/settings/{guild_id}", headers=bot_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["prefix"] == "!"

        # 3. Update settings (via bot)
        update_response = await client.put(
            f"/api/v1/settings/{guild_id}",
            headers=bot_headers,
            json={"prefix": ">>", "welcome_enabled": True},
        )
        assert update_response.status_code == 200
        assert update_response.json()["prefix"] == ">>"
        assert update_response.json()["welcome_enabled"] is True

        # 4. Verify update persisted
        verify_response = await client.get(
            f"/api/v1/settings/{guild_id}", headers=bot_headers
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["prefix"] == ">>"

        # 5. Delete settings (via admin)
        delete_response = await client.delete(
            f"/api/v1/settings/{guild_id}", headers=admin_headers
        )
        assert delete_response.status_code == 200

        # 6. Verify deletion
        gone_response = await client.get(
            f"/api/v1/settings/{guild_id}", headers=bot_headers
        )
        assert gone_response.status_code == 404

    async def test_duplicate_settings_rejected(
        self, client: AsyncClient, bot_headers
    ):
        guild_id = "666777888999"

        # Create settings
        await client.post(
            "/api/v1/settings",
            headers=bot_headers,
            json={"guild_id": guild_id, "prefix": "!"},
        )

        # Try to create again
        response = await client.post(
            "/api/v1/settings",
            headers=bot_headers,
            json={"guild_id": guild_id, "prefix": "?"},
        )
        assert response.status_code == 400


class TestHealthCheck:
    """Test health and root endpoints."""

    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_root(self, client: AsyncClient):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["status"] == "running"
