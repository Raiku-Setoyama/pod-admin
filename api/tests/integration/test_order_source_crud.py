"""受注元（OrderSource）CRUD APIの統合テスト

FEAT-0014: 受注元管理CRUD

テスト対象: /api/v1/order-sources エンドポイント
- AC-001: GET /order-sources で受注元一覧を取得できる
- AC-002: GET /order-sources でis_activeフィルターが動作する
- AC-003: GET /order-sources/{id} で受注元詳細を取得できる
- AC-004: GET /order-sources/{id} で存在しないIDを指定すると404が返る
- AC-005: POST /order-sources で受注元を作成できる
- AC-006: POST /order-sources で重複するcodeを指定すると409エラーが返る
- AC-007: POST /order-sources で重複するapi_keyを指定すると409エラーが返る
- AC-008: PATCH /order-sources/{id} で受注元を更新できる
- AC-009: DELETE /order-sources/{id} で受注元を削除できる
- AC-010: 認証なしでAPIにアクセスすると401が返る
"""

import pytest
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


# APIプレフィックス
API_PREFIX = settings.API_V1_PREFIX


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def test_order_source_for_crud(db_session: AsyncSession):
    """CRUD テスト用の受注元を作成"""
    source_id = str(uuid4())
    source_code = f"CRUD{source_id[:6].upper()}"
    api_key = f"crud-api-key-{source_id}"

    await db_session.execute(
        text("""
            INSERT INTO order_sources (id, code, name, api_key, phone, postal_code, address_prefecture, address_city, is_active, created_at, updated_at)
            VALUES (:id, :code, :name, :api_key, :phone, :postal_code, :address_prefecture, :address_city, :is_active, NOW(), NOW())
        """),
        {
            "id": source_id,
            "code": source_code,
            "name": "CRUD Test Source",
            "api_key": api_key,
            "phone": "03-1234-5678",
            "postal_code": "100-0001",
            "address_prefecture": "東京都",
            "address_city": "千代田区1-1-1",
            "is_active": True,
        }
    )
    await db_session.commit()

    yield {
        "id": source_id,
        "code": source_code,
        "api_key": api_key,
        "name": "CRUD Test Source",
    }


@pytest.fixture
async def test_inactive_order_source(db_session: AsyncSession):
    """無効な受注元を作成"""
    source_id = str(uuid4())
    source_code = f"INACT{source_id[:5].upper()}"

    await db_session.execute(
        text("""
            INSERT INTO order_sources (id, code, name, api_key, phone, postal_code, address_prefecture, address_city, is_active, created_at, updated_at)
            VALUES (:id, :code, :name, :api_key, :phone, :postal_code, :address_prefecture, :address_city, :is_active, NOW(), NOW())
        """),
        {
            "id": source_id,
            "code": source_code,
            "name": "Inactive Source",
            "api_key": f"inactive-api-key-{source_id}",
            "phone": "03-9999-8888",
            "postal_code": "150-0001",
            "address_prefecture": "東京都",
            "address_city": "渋谷区",
            "is_active": False,
        }
    )
    await db_session.commit()

    yield {
        "id": source_id,
        "code": source_code,
        "name": "Inactive Source",
    }


# ---------------------------------------------------------------------------
# AC-001: GET /order-sources で受注元一覧を取得できる
# ---------------------------------------------------------------------------

class TestListOrderSources:
    """GET /order-sources 一覧取得テスト"""

    @pytest.mark.asyncio
    async def test_ac001_list_order_sources(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_source_for_crud: dict,
    ):
        """AC-001: GET /order-sources で受注元一覧を取得できる

        given: 受注元が登録されている
        when: GET /api/v1/order-sources を管理者トークンで呼び出す
        then: items配列に受注元一覧、total、page、limitが返される
        """
        response = await client.get(
            f"{API_PREFIX}/order-sources",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 1

    # ---------------------------------------------------------------------------
    # AC-002: GET /order-sources でis_activeフィルターが動作する
    # ---------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac002_list_order_sources_is_active_filter(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_source_for_crud: dict,
        test_inactive_order_source: dict,
    ):
        """AC-002: GET /order-sources でis_activeフィルターが動作する

        given: 有効・無効の受注元が混在している
        when: GET /api/v1/order-sources?is_active=true を呼び出す
        then: is_active=trueの受注元のみが返される
        """
        response = await client.get(
            f"{API_PREFIX}/order-sources?is_active=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # 全てのアイテムがis_active=trueであること
        for item in data["items"]:
            assert item["is_active"] is True

    @pytest.mark.asyncio
    async def test_ac002_list_order_sources_is_active_false_filter(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_source_for_crud: dict,
        test_inactive_order_source: dict,
    ):
        """is_active=falseフィルターで無効な受注元のみが返される

        given: 有効・無効の受注元が混在している
        when: GET /api/v1/order-sources?is_active=false を呼び出す
        then: is_active=falseの受注元のみが返される
        """
        response = await client.get(
            f"{API_PREFIX}/order-sources?is_active=false",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["is_active"] is False


# ---------------------------------------------------------------------------
# AC-003/004: GET /order-sources/{id} 詳細取得テスト
# ---------------------------------------------------------------------------

class TestGetOrderSource:
    """GET /order-sources/{id} 詳細取得テスト"""

    @pytest.mark.asyncio
    async def test_ac003_get_order_source_by_id(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_source_for_crud: dict,
    ):
        """AC-003: GET /order-sources/{id} で受注元詳細を取得できる

        given: 受注元が登録されている
        when: GET /api/v1/order-sources/{id} を管理者トークンで呼び出す
        then: 指定IDの受注元情報が返される
        """
        source_id = test_order_source_for_crud["id"]
        response = await client.get(
            f"{API_PREFIX}/order-sources/{source_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == source_id
        assert data["code"] == test_order_source_for_crud["code"]
        assert data["name"] == "CRUD Test Source"
        assert "phone" in data
        assert "postal_code" in data
        assert "address_prefecture" in data
        assert "address_city" in data
        assert "is_active" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_ac004_get_order_source_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """AC-004: GET /order-sources/{id} で存在しないIDを指定すると404が返る

        given: 指定IDの受注元が存在しない
        when: GET /api/v1/order-sources/{存在しないID} を呼び出す
        then: 404エラーが返される
        """
        non_existent_id = str(uuid4())
        response = await client.get(
            f"{API_PREFIX}/order-sources/{non_existent_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# AC-005: POST /order-sources で受注元を作成できる
# ---------------------------------------------------------------------------

class TestCreateOrderSource:
    """POST /order-sources 作成テスト"""

    @pytest.mark.asyncio
    async def test_ac005_create_order_source(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """AC-005: POST /order-sources で受注元を作成できる

        given: 管理者としてログインしている
        when: POST /api/v1/order-sources に必要フィールドを含むJSONを送信する
        then: 201ステータスで作成された受注元情報が返される
        """
        unique_suffix = str(uuid4())[:8]
        create_data = {
            "code": f"NEW{unique_suffix}",
            "name": "新規受注元",
            "api_key": f"new-key-{unique_suffix}",
            "phone": "03-5555-6666",
            "postal_code": "100-0001",
            "address_prefecture": "東京都",
            "address_city": "千代田区丸の内1-1-1",
            "address_building": "テストビル3F",
        }

        response = await client.post(
            f"{API_PREFIX}/order-sources",
            json=create_data,
            headers=auth_headers,
        )

        assert response.status_code == 201, (
            f"Expected 201, got {response.status_code}: {response.json()}"
        )

        data = response.json()
        assert data["code"] == create_data["code"]
        assert data["name"] == "新規受注元"
        assert data["phone"] == "03-5555-6666"
        assert data["postal_code"] == "100-0001"
        assert data["address_prefecture"] == "東京都"
        assert data["address_city"] == "千代田区丸の内1-1-1"
        assert data["address_building"] == "テストビル3F"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    # ---------------------------------------------------------------------------
    # AC-006: POST /order-sources で重複するcodeを指定すると409エラーが返る
    # ---------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac006_create_duplicate_code_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_source_for_crud: dict,
    ):
        """AC-006: POST /order-sources で重複するcodeを指定すると409エラーが返る

        given: code="RKSYO"の受注元が既に存在する
        when: POST /api/v1/order-sources で同じcodeを送信する
        then: 409 Conflictエラーが返される
        """
        create_data = {
            "code": test_order_source_for_crud["code"],  # 既存のcodeと重複
            "name": "重複コードテスト",
            "api_key": f"unique-key-{uuid4()}",
            "phone": "03-0000-0000",
            "postal_code": "100-0001",
            "address_prefecture": "東京都",
            "address_city": "千代田区",
        }

        response = await client.post(
            f"{API_PREFIX}/order-sources",
            json=create_data,
            headers=auth_headers,
        )

        assert response.status_code == 409, (
            f"Expected 409 for duplicate code, got {response.status_code}: {response.json()}"
        )

    # ---------------------------------------------------------------------------
    # AC-007: POST /order-sources で重複するapi_keyを指定すると409エラーが返る
    # ---------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ac007_create_duplicate_api_key_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_source_for_crud: dict,
    ):
        """AC-007: POST /order-sources で重複するapi_keyを指定すると409エラーが返る

        given: あるapi_keyの受注元が既に存在する
        when: POST /api/v1/order-sources で同じapi_keyを送信する
        then: 409 Conflictエラーが返される
        """
        create_data = {
            "code": f"UNIQ{str(uuid4())[:6]}",
            "name": "重複APIキーテスト",
            "api_key": test_order_source_for_crud["api_key"],  # 既存のapi_keyと重複
            "phone": "03-0000-0000",
            "postal_code": "100-0001",
            "address_prefecture": "東京都",
            "address_city": "千代田区",
        }

        response = await client.post(
            f"{API_PREFIX}/order-sources",
            json=create_data,
            headers=auth_headers,
        )

        assert response.status_code == 409, (
            f"Expected 409 for duplicate api_key, got {response.status_code}: {response.json()}"
        )


# ---------------------------------------------------------------------------
# AC-008: PATCH /order-sources/{id} で受注元を更新できる
# ---------------------------------------------------------------------------

class TestUpdateOrderSource:
    """PATCH /order-sources/{id} 更新テスト"""

    @pytest.mark.asyncio
    async def test_ac008_update_order_source(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_order_source_for_crud: dict,
    ):
        """AC-008: PATCH /order-sources/{id} で受注元を更新できる

        given: 受注元が登録されている
        when: PATCH /api/v1/order-sources/{id} に変更フィールドを含むJSONを送信する
        then: 200ステータスで更新された受注元情報が返される
        """
        source_id = test_order_source_for_crud["id"]
        update_data = {
            "name": "更新後の受注元名",
            "phone": "03-9999-0000",
        }

        response = await client.patch(
            f"{API_PREFIX}/order-sources/{source_id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.json()}"
        )

        data = response.json()
        assert data["id"] == source_id
        assert data["name"] == "更新後の受注元名"
        assert data["phone"] == "03-9999-0000"

    @pytest.mark.asyncio
    async def test_update_order_source_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """存在しないIDを更新しようとすると404が返る"""
        non_existent_id = str(uuid4())
        update_data = {"name": "更新テスト"}

        response = await client.patch(
            f"{API_PREFIX}/order-sources/{non_existent_id}",
            json=update_data,
            headers=auth_headers,
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# AC-009: DELETE /order-sources/{id} で受注元を削除できる
# ---------------------------------------------------------------------------

class TestDeleteOrderSource:
    """DELETE /order-sources/{id} 削除テスト"""

    @pytest.mark.asyncio
    async def test_ac009_delete_order_source(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """AC-009: DELETE /order-sources/{id} で受注元を削除できる

        given: 受注元が登録されている
        when: DELETE /api/v1/order-sources/{id} を管理者トークンで呼び出す
        then: 204ステータスが返され、受注元が削除される
        """
        # テスト用の受注元を作成（削除テスト専用）
        source_id = str(uuid4())
        source_code = f"DEL{source_id[:7].upper()}"
        await db_session.execute(
            text("""
                INSERT INTO order_sources (id, code, name, api_key, phone, postal_code, address_prefecture, address_city, is_active, created_at, updated_at)
                VALUES (:id, :code, :name, :api_key, :phone, :postal_code, :address_prefecture, :address_city, :is_active, NOW(), NOW())
            """),
            {
                "id": source_id,
                "code": source_code,
                "name": "Delete Test Source",
                "api_key": f"delete-key-{source_id}",
                "phone": "03-0000-0000",
                "postal_code": "100-0001",
                "address_prefecture": "東京都",
                "address_city": "千代田区",
                "is_active": True,
            }
        )
        await db_session.commit()

        response = await client.delete(
            f"{API_PREFIX}/order-sources/{source_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # 削除後にGETすると404が返ることを確認
        get_response = await client.get(
            f"{API_PREFIX}/order-sources/{source_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_order_source_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """存在しないIDを削除しようとすると404が返る"""
        non_existent_id = str(uuid4())
        response = await client.delete(
            f"{API_PREFIX}/order-sources/{non_existent_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# AC-010: 認証なしでAPIにアクセスすると401が返る
# ---------------------------------------------------------------------------

class TestOrderSourceAuthentication:
    """認証テスト"""

    @pytest.mark.asyncio
    async def test_ac010_unauthenticated_list_returns_401(
        self,
        client: AsyncClient,
    ):
        """AC-010: 認証なしでGET /order-sourcesにアクセスすると401が返る

        given: 認証トークンなし
        when: GET /api/v1/order-sources を呼び出す
        then: 401 Unauthorizedエラーが返される
        """
        response = await client.get(f"{API_PREFIX}/order-sources")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_ac010_unauthenticated_create_returns_401(
        self,
        client: AsyncClient,
    ):
        """認証なしでPOST /order-sourcesにアクセスすると401が返る"""
        create_data = {
            "code": "NOAUTH",
            "name": "認証なしテスト",
            "api_key": "no-auth-key",
            "phone": "03-0000-0000",
            "postal_code": "100-0001",
            "address_prefecture": "東京都",
            "address_city": "千代田区",
        }

        response = await client.post(
            f"{API_PREFIX}/order-sources",
            json=create_data,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_ac010_unauthenticated_get_returns_401(
        self,
        client: AsyncClient,
    ):
        """認証なしでGET /order-sources/{id}にアクセスすると401が返る"""
        response = await client.get(
            f"{API_PREFIX}/order-sources/{uuid4()}",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_ac010_unauthenticated_update_returns_401(
        self,
        client: AsyncClient,
    ):
        """認証なしでPATCH /order-sources/{id}にアクセスすると401が返る"""
        response = await client.patch(
            f"{API_PREFIX}/order-sources/{uuid4()}",
            json={"name": "更新テスト"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_ac010_unauthenticated_delete_returns_401(
        self,
        client: AsyncClient,
    ):
        """認証なしでDELETE /order-sources/{id}にアクセスすると401が返る"""
        response = await client.delete(
            f"{API_PREFIX}/order-sources/{uuid4()}",
        )

        assert response.status_code == 401
