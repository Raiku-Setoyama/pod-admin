"""Integration tests for authentication token expiry.

FEAT-0030: リフレッシュトークンの有効期限を7日から30日に変更。
管理者・製造者の両方でログインAPIから返されるリフレッシュトークンの
有効期限が30日であることを検証する。
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.config import settings
from app.utils.security import ALGORITHM, create_refresh_token, hash_password


@pytest.fixture
async def test_admin_for_auth(db_session: AsyncSession):
    """認証テスト用の管理者ユーザーを作成"""
    user_id = str(uuid4())

    await db_session.execute(
        text("""
            INSERT INTO users (id, email, name, password_hash, role, is_active, created_at, updated_at)
            VALUES (:id, :email, :name, :password_hash, :role, :is_active, NOW(), NOW())
        """),
        {
            "id": user_id,
            "email": f"auth-test-admin-{user_id[:8]}@example.com",
            "name": "Auth Test Admin",
            "password_hash": hash_password("test-password-123"),
            "role": "admin",
            "is_active": True,
        },
    )
    await db_session.commit()

    yield {
        "id": user_id,
        "email": f"auth-test-admin-{user_id[:8]}@example.com",
        "password": "test-password-123",
    }


@pytest.fixture
async def test_manufacturer_for_auth(db_session: AsyncSession):
    """認証テスト用の製造者を作成"""
    manufacturer_id = str(uuid4())

    await db_session.execute(
        text("""
            INSERT INTO manufacturers (
                id, name, email, supported_products, unit_prices,
                lead_time_days, daily_order_limit, sharing_method,
                password_hash, is_active, created_at, updated_at
            )
            VALUES (
                :id, :name, :email, :supported_products, :unit_prices,
                :lead_time_days, :daily_order_limit, :sharing_method,
                :password_hash, :is_active, NOW(), NOW()
            )
        """),
        {
            "id": manufacturer_id,
            "name": f"Auth Test Manufacturer {manufacturer_id[:8]}",
            "email": f"auth-test-mfr-{manufacturer_id[:8]}@example.com",
            "supported_products": ["seal"],
            "unit_prices": "{}",
            "lead_time_days": 3,
            "daily_order_limit": 100,
            "sharing_method": "portal",
            "password_hash": hash_password("test-password-123"),
            "is_active": True,
        },
    )
    await db_session.commit()

    yield {
        "id": manufacturer_id,
        "email": f"auth-test-mfr-{manufacturer_id[:8]}@example.com",
        "password": "test-password-123",
    }


@pytest.mark.asyncio
async def test_admin_login_returns_30_day_refresh_token(
    client: AsyncClient,
    test_admin_for_auth: dict,
):
    """AC-002: 管理者ログインで30日有効のリフレッシュトークンが返される"""
    before = datetime.now(timezone.utc)

    response = await client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        json={
            "email": test_admin_for_auth["email"],
            "password": test_admin_for_auth["password"],
        },
    )

    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "refresh_token" in data

    # リフレッシュトークンのexpを検証
    decoded = jwt.decode(
        data["refresh_token"], settings.SECRET_KEY, algorithms=[ALGORITHM]
    )
    exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)

    expected_min = before + timedelta(days=30) - timedelta(seconds=60)
    expected_max = before + timedelta(days=30) + timedelta(seconds=60)

    assert expected_min <= exp <= expected_max, (
        f"Admin refresh token exp should be ~30 days. Got {exp}"
    )


@pytest.mark.asyncio
async def test_manufacturer_login_returns_30_day_refresh_token(
    client: AsyncClient,
    test_manufacturer_for_auth: dict,
):
    """AC-003: 製造者ログインで30日有効のリフレッシュトークンが返される"""
    before = datetime.now(timezone.utc)

    response = await client.post(
        f"{settings.API_V1_PREFIX}/manufacturer-portal/login",
        json={
            "email": test_manufacturer_for_auth["email"],
            "password": test_manufacturer_for_auth["password"],
        },
    )

    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "refresh_token" in data

    # リフレッシュトークンのexpを検証
    decoded = jwt.decode(
        data["refresh_token"], settings.SECRET_KEY, algorithms=[ALGORITHM]
    )
    exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)

    expected_min = before + timedelta(days=30) - timedelta(seconds=60)
    expected_max = before + timedelta(days=30) + timedelta(seconds=60)

    assert expected_min <= exp <= expected_max, (
        f"Manufacturer refresh token exp should be ~30 days. Got {exp}"
    )


@pytest.mark.asyncio
async def test_refresh_endpoint_returns_new_30_day_token(
    client: AsyncClient,
    test_admin_for_auth: dict,
):
    """AC-004: リフレッシュトークンが有効な間、アクセストークンの再発行が可能"""
    # まずログインしてリフレッシュトークンを取得
    login_response = await client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        json={
            "email": test_admin_for_auth["email"],
            "password": test_admin_for_auth["password"],
        },
    )
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    # リフレッシュエンドポイントを呼び出し
    before = datetime.now(timezone.utc)
    refresh_response = await client.post(
        f"{settings.API_V1_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 200, f"Refresh failed: {refresh_response.text}"
    data = refresh_response.json()
    assert "access_token" in data
    assert "refresh_token" in data

    # 新しいリフレッシュトークンも30日の有効期限を持つこと
    decoded = jwt.decode(
        data["refresh_token"], settings.SECRET_KEY, algorithms=[ALGORITHM]
    )
    exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)

    expected_min = before + timedelta(days=30) - timedelta(seconds=60)
    expected_max = before + timedelta(days=30) + timedelta(seconds=60)

    assert expected_min <= exp <= expected_max, (
        f"Refreshed token exp should be ~30 days. Got {exp}"
    )
