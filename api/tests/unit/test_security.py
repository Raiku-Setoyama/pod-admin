"""Test security utilities."""

from datetime import timedelta

from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password() -> None:
    """Test password hashing."""
    password = "test_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$2b$")  # bcrypt prefix


def test_verify_password_correct() -> None:
    """Test verifying correct password."""
    password = "test_password_123"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect() -> None:
    """Test verifying incorrect password."""
    password = "test_password_123"
    wrong_password = "wrong_password"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False


def test_create_access_token() -> None:
    """Test creating access token."""
    data = {"sub": "user_id_123", "role": "admin"}
    token = create_access_token(data)

    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token() -> None:
    """Test creating refresh token."""
    data = {"sub": "user_id_123"}
    token = create_refresh_token(data)

    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_token_valid() -> None:
    """Test decoding a valid token."""
    data = {"sub": "user_id_123", "role": "admin"}
    token = create_access_token(data)
    decoded = decode_token(token)

    assert decoded is not None
    assert decoded["sub"] == "user_id_123"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert decoded["type"] == "access"


def test_decode_token_expired() -> None:
    """Test decoding an expired token."""
    data = {"sub": "user_id_123"}
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))
    decoded = decode_token(token)

    assert decoded is None


def test_decode_token_invalid() -> None:
    """Test decoding an invalid token."""
    decoded = decode_token("invalid_token")

    assert decoded is None


def test_access_and_refresh_tokens_different() -> None:
    """Test that access and refresh tokens have different types."""
    data = {"sub": "user_id_123"}
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    access_decoded = decode_token(access_token)
    refresh_decoded = decode_token(refresh_token)

    assert access_decoded["type"] == "access"
    assert refresh_decoded["type"] == "refresh"
