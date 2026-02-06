"""Tests for security utilities."""

import pytest

from api.core.jwt_handler import (
    create_access_token,
    create_refresh_token,
    is_token_expired,
    verify_token,
)
from api.core.security import get_password_hash, verify_password


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_hash_password(self):
        hashed = get_password_hash("TestPassword123")
        assert hashed != "TestPassword123"
        assert len(hashed) > 0

    def test_verify_correct_password(self):
        hashed = get_password_hash("TestPassword123")
        assert verify_password("TestPassword123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("TestPassword123")
        assert verify_password("WrongPassword", hashed) is False


class TestJWT:
    """Tests for JWT token operations."""

    def test_create_access_token(self):
        token = create_access_token(subject=1)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_access_token(self):
        token = create_access_token(subject=42)
        payload = verify_token(token)
        assert payload is not None
        assert payload.sub == "42"
        assert payload.type == "access"

    def test_verify_invalid_token(self):
        payload = verify_token("invalid.token.here")
        assert payload is None

    def test_refresh_token_not_valid_as_access(self):
        token = create_refresh_token(subject=1)
        payload = verify_token(token, token_type="access")
        assert payload is None

    def test_access_token_not_valid_as_refresh(self):
        token = create_access_token(subject=1)
        payload = verify_token(token, token_type="refresh")
        assert payload is None
