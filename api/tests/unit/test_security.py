"""Test security utilities."""

import pytest
from datetime import datetime, timedelta, timezone

from app.utils.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings


def test_hash_password():
    """Test password hashing."""
    password = "test_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$2b$")  # bcrypt prefix


def test_verify_password_correct():
    """Test verifying correct password."""
    password = "test_password_123"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Test verifying incorrect password."""
    password = "test_password_123"
    wrong_password = "wrong_password"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False


def test_create_access_token():
    """Test creating access token."""
    data = {"sub": "user_id_123", "role": "admin"}
    token = create_access_token(data)

    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token():
    """Test creating refresh token."""
    data = {"sub": "user_id_123"}
    token = create_refresh_token(data)

    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_token_valid():
    """Test decoding a valid token."""
    data = {"sub": "user_id_123", "role": "admin"}
    token = create_access_token(data)
    decoded = decode_token(token)

    assert decoded is not None
    assert decoded["sub"] == "user_id_123"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert decoded["type"] == "access"


def test_decode_token_expired():
    """Test decoding an expired token."""
    data = {"sub": "user_id_123"}
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))
    decoded = decode_token(token)

    assert decoded is None


def test_decode_token_invalid():
    """Test decoding an invalid token."""
    decoded = decode_token("invalid_token")

    assert decoded is None


def test_access_and_refresh_tokens_different():
    """Test that access and refresh tokens have different types."""
    data = {"sub": "user_id_123"}
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    access_decoded = decode_token(access_token)
    refresh_decoded = decode_token(refresh_token)

    assert access_decoded["type"] == "access"
    assert refresh_decoded["type"] == "refresh"


# === FEAT-0030: リフレッシュトークン有効期限30日テスト ===


def test_refresh_token_expiry_is_30_days():
    """AC-001: リフレッシュトークンが30日の有効期限で発行される"""
    from jose import jwt

    data = {"sub": "user_id_123"}
    before = datetime.now(timezone.utc)
    token = create_refresh_token(data)
    after = datetime.now(timezone.utc)

    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)

    # expが発行時刻から30日後（±60秒の許容範囲）であること
    expected_min = before + timedelta(days=30) - timedelta(seconds=60)
    expected_max = after + timedelta(days=30) + timedelta(seconds=60)

    assert expected_min <= exp <= expected_max, (
        f"Refresh token exp should be ~30 days from now. "
        f"Got {exp}, expected between {expected_min} and {expected_max}"
    )


def test_refresh_token_default_expiry_uses_settings():
    """設定値REFRESH_TOKEN_EXPIRE_DAYSがリフレッシュトークンに反映されること"""
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30, (
        f"REFRESH_TOKEN_EXPIRE_DAYS should be 30, got {settings.REFRESH_TOKEN_EXPIRE_DAYS}"
    )


def test_refresh_token_expired_after_30_days():
    """AC-005: 30日超過のリフレッシュトークンは無効と判定される"""
    data = {"sub": "user_id_123"}
    # 31日前に発行されたトークンをシミュレート（負のtimedelta）
    expired_token = create_refresh_token(
        data, expires_delta=timedelta(days=-1)
    )
    decoded = decode_token(expired_token)

    assert decoded is None, "Expired refresh token should be decoded as None"


def test_access_token_expiry_unchanged():
    """アクセストークンの有効期限が30分のままであること（変更なし）"""
    from jose import jwt

    data = {"sub": "user_id_123", "role": "admin"}
    before = datetime.now(timezone.utc)
    token = create_access_token(data)

    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)

    # expが発行時刻から30分後（±60秒の許容範囲）であること
    expected_min = before + timedelta(minutes=30) - timedelta(seconds=60)
    expected_max = before + timedelta(minutes=30) + timedelta(seconds=60)

    assert expected_min <= exp <= expected_max, (
        f"Access token exp should be ~30 minutes from now. "
        f"Got {exp}, expected between {expected_min} and {expected_max}"
    )
