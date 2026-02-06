"""Tests for authentication API endpoints."""

import pytest
from httpx import AsyncClient


class TestRegister:
    """Tests for user registration."""

    async def test_register_success(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "ValidPass123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert data["is_active"] is True

    async def test_register_duplicate_username(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "different@example.com",
                "password": "ValidPass123",
            },
        )
        assert response.status_code == 400
        assert "Username already registered" in response.json()["detail"]

    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "differentuser",
                "email": "test@example.com",
                "password": "ValidPass123",
            },
        )
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    async def test_register_weak_password(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "weak",
            },
        )
        assert response.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "not-an-email",
                "password": "ValidPass123",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """Tests for user login."""

    async def test_login_success(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "TestPassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "WrongPassword123"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "SomePassword123"},
        )
        assert response.status_code == 401


class TestTokenRefresh:
    """Tests for token refresh."""

    async def test_refresh_token_success(self, client: AsyncClient, test_user):
        # First login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "TestPassword123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh the token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401


class TestCurrentUser:
    """Tests for current user endpoints."""

    async def test_get_me(self, client: AsyncClient, test_user, auth_headers):
        response = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    async def test_get_me_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_update_me(self, client: AsyncClient, test_user, auth_headers):
        response = await client.patch(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={"display_name": "Test Display Name"},
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "Test Display Name"


class TestPasswordChange:
    """Tests for password change."""

    async def test_change_password_success(
        self, client: AsyncClient, test_user, auth_headers
    ):
        response = await client.post(
            "/api/v1/auth/password/change",
            headers=auth_headers,
            json={
                "current_password": "TestPassword123",
                "new_password": "NewPassword456",
            },
        )
        assert response.status_code == 200

    async def test_change_password_wrong_current(
        self, client: AsyncClient, test_user, auth_headers
    ):
        response = await client.post(
            "/api/v1/auth/password/change",
            headers=auth_headers,
            json={
                "current_password": "WrongPassword123",
                "new_password": "NewPassword456",
            },
        )
        assert response.status_code == 400
