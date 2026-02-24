"""OrderSourceService のユニットテスト

FEAT-0014: 受注元（OrderSource）CRUD管理

テスト対象: OrderSourceService
- AC-011: create/get_by_id/list/update/deleteメソッドがリポジトリを通じてCRUD操作を行う
- AC-012: 重複code/api_keyを検知しConflictError（DuplicateError）をraiseする
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.order_source_service import OrderSourceService
from app.schemas.order_source import (
    OrderSourceCreate,
    OrderSourceUpdate,
    OrderSourceResponse,
    OrderSourceListResponse,
)
from app.utils.exceptions import DuplicateError, NotFoundError


# ---------------------------------------------------------------------------
# Helper: mock OrderSource model factory
# ---------------------------------------------------------------------------

def _make_order_source(
    *,
    id: str | None = None,
    code: str = "RKSYO",
    name: str = "楽商",
    api_key: str = "test-api-key-001",
    phone: str = "03-1234-5678",
    postal_code: str = "100-0001",
    address_prefecture: str = "東京都",
    address_city: str = "千代田区1-1-1",
    address_building: str | None = None,
    is_active: bool = True,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> MagicMock:
    """Create a mock OrderSource model instance."""
    order_source = MagicMock()
    order_source.id = id or str(uuid4())
    order_source.code = code
    order_source.name = name
    order_source.api_key = api_key
    order_source.phone = phone
    order_source.postal_code = postal_code
    order_source.address_prefecture = address_prefecture
    order_source.address_city = address_city
    order_source.address_building = address_building
    order_source.is_active = is_active
    order_source.created_at = created_at or datetime(2026, 1, 1, 0, 0, 0)
    order_source.updated_at = updated_at or datetime(2026, 1, 1, 0, 0, 0)
    return order_source


# ---------------------------------------------------------------------------
# AC-011: OrderSourceServiceがリポジトリを通じてCRUD操作を行う
# ---------------------------------------------------------------------------

class TestOrderSourceServiceCRUD:
    """AC-011: OrderSourceServiceのCRUD操作テスト"""

    @pytest.fixture
    def mock_order_source_repo(self):
        """モック OrderSourceRepository"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_source_repo):
        """テスト対象のサービスインスタンス"""
        return OrderSourceService(order_source_repo=mock_order_source_repo)

    # --- create ---

    @pytest.mark.asyncio
    async def test_create_order_source_success(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """受注元を正常に作成できる

        given: 重複するcode/api_keyが存在しない
        when: createメソッドを呼び出す
        then: リポジトリのcreateが呼ばれ、OrderSourceResponseが返される
        """
        mock_order_source_repo.find_by_code.return_value = None
        mock_order_source_repo.find_by_api_key.return_value = None

        created_source = _make_order_source(
            code="NEWCODE",
            name="新しい受注元",
            api_key="new-api-key-001",
            phone="090-1111-2222",
            postal_code="150-0001",
            address_prefecture="東京都",
            address_city="渋谷区1-1-1",
        )
        mock_order_source_repo.create.return_value = created_source

        data = OrderSourceCreate(
            code="NEWCODE",
            name="新しい受注元",
            api_key="new-api-key-001",
            phone="090-1111-2222",
            postal_code="150-0001",
            address_prefecture="東京都",
            address_city="渋谷区1-1-1",
        )

        result = await service.create(data)

        # リポジトリの重複チェックが呼ばれたことを確認
        mock_order_source_repo.find_by_code.assert_called_once_with("NEWCODE")
        mock_order_source_repo.find_by_api_key.assert_called_once_with("new-api-key-001")
        # リポジトリのcreateが呼ばれたことを確認
        mock_order_source_repo.create.assert_called_once()
        # 正しいレスポンスが返されることを確認
        assert isinstance(result, OrderSourceResponse)
        assert result.code == "NEWCODE"
        assert result.name == "新しい受注元"

    # --- get_by_id ---

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """IDで受注元を取得できる

        given: 指定IDの受注元が存在する
        when: get_by_idメソッドを呼び出す
        then: OrderSourceResponseが返される
        """
        source_id = str(uuid4())
        mock_source = _make_order_source(id=source_id, code="RKSYO")
        mock_order_source_repo.find_by_id.return_value = mock_source

        result = await service.get_by_id(source_id)

        mock_order_source_repo.find_by_id.assert_called_once_with(source_id)
        assert isinstance(result, OrderSourceResponse)
        assert result.id == source_id
        assert result.code == "RKSYO"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """存在しないIDの場合NotFoundErrorがraiseされる

        given: 指定IDの受注元が存在しない
        when: get_by_idメソッドを呼び出す
        then: NotFoundErrorがraiseされる
        """
        mock_order_source_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_by_id("non-existent-id")

        assert exc_info.value.status_code == 404

    # --- list ---

    @pytest.mark.asyncio
    async def test_list_order_sources_success(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """受注元一覧を取得できる

        given: 受注元が複数登録されている
        when: listメソッドを呼び出す
        then: OrderSourceListResponseが返される
        """
        sources = [
            _make_order_source(code="SRC-001", name="受注元1"),
            _make_order_source(code="SRC-002", name="受注元2"),
        ]
        mock_order_source_repo.find_all.return_value = (sources, 2)

        result = await service.list(page=1, limit=20)

        mock_order_source_repo.find_all.assert_called_once_with(
            page=1, limit=20, is_active=None
        )
        assert isinstance(result, OrderSourceListResponse)
        assert len(result.items) == 2
        assert result.total == 2
        assert result.page == 1
        assert result.limit == 20

    @pytest.mark.asyncio
    async def test_list_order_sources_with_is_active_filter(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """is_activeフィルター付きで受注元一覧を取得できる

        given: 有効・無効の受注元が混在している
        when: is_active=Trueでlistメソッドを呼び出す
        then: find_allにis_active=Trueが渡される
        """
        active_source = _make_order_source(code="ACTIVE", is_active=True)
        mock_order_source_repo.find_all.return_value = ([active_source], 1)

        result = await service.list(page=1, limit=20, is_active=True)

        mock_order_source_repo.find_all.assert_called_once_with(
            page=1, limit=20, is_active=True
        )
        assert len(result.items) == 1

    # --- update ---

    @pytest.mark.asyncio
    async def test_update_order_source_success(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """受注元を正常に更新できる

        given: 受注元が登録されている
        when: updateメソッドを呼び出す
        then: リポジトリのupdateが呼ばれ、OrderSourceResponseが返される
        """
        source_id = str(uuid4())
        existing_source = _make_order_source(id=source_id, code="OLD", name="旧名前")
        mock_order_source_repo.find_by_id.return_value = existing_source

        # 更新後のモックを設定
        updated_source = _make_order_source(id=source_id, code="OLD", name="新名前")
        mock_order_source_repo.update.return_value = updated_source

        data = OrderSourceUpdate(name="新名前")
        result = await service.update(source_id, data)

        mock_order_source_repo.find_by_id.assert_called_once_with(source_id)
        mock_order_source_repo.update.assert_called_once()
        assert isinstance(result, OrderSourceResponse)

    @pytest.mark.asyncio
    async def test_update_order_source_not_found(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """存在しないIDを更新しようとするとNotFoundErrorがraiseされる

        given: 指定IDの受注元が存在しない
        when: updateメソッドを呼び出す
        then: NotFoundErrorがraiseされる
        """
        mock_order_source_repo.find_by_id.return_value = None

        data = OrderSourceUpdate(name="新名前")
        with pytest.raises(NotFoundError) as exc_info:
            await service.update("non-existent-id", data)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_order_source_duplicate_code(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """更新時に重複するcodeを指定するとDuplicateErrorがraiseされる

        given: 別の受注元が同じcodeを持っている
        when: updateメソッドでそのcodeに変更する
        then: DuplicateErrorがraiseされる
        """
        source_id = str(uuid4())
        existing_source = _make_order_source(id=source_id, code="ORIGINAL")
        mock_order_source_repo.find_by_id.return_value = existing_source

        # 別の受注元が既に同じcodeを使用中
        another_source = _make_order_source(id=str(uuid4()), code="DUPLICATE")
        mock_order_source_repo.find_by_code.return_value = another_source

        data = OrderSourceUpdate(code="DUPLICATE")
        with pytest.raises(DuplicateError) as exc_info:
            await service.update(source_id, data)

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_update_order_source_duplicate_api_key(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """更新時に重複するapi_keyを指定するとDuplicateErrorがraiseされる

        given: 別の受注元が同じapi_keyを持っている
        when: updateメソッドでそのapi_keyに変更する
        then: DuplicateErrorがraiseされる
        """
        source_id = str(uuid4())
        existing_source = _make_order_source(id=source_id, api_key="original-key")
        mock_order_source_repo.find_by_id.return_value = existing_source

        # codeの重複はなし
        mock_order_source_repo.find_by_code.return_value = None
        # 別の受注元が既に同じapi_keyを使用中
        another_source = _make_order_source(id=str(uuid4()), api_key="duplicate-key")
        mock_order_source_repo.find_by_api_key.return_value = another_source

        data = OrderSourceUpdate(api_key="duplicate-key")
        with pytest.raises(DuplicateError) as exc_info:
            await service.update(source_id, data)

        assert exc_info.value.status_code == 409

    # --- delete ---

    @pytest.mark.asyncio
    async def test_delete_order_source_success(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """受注元を正常に削除できる

        given: 受注元が登録されている
        when: deleteメソッドを呼び出す
        then: リポジトリのdeleteが呼ばれる
        """
        source_id = str(uuid4())
        existing_source = _make_order_source(id=source_id)
        mock_order_source_repo.find_by_id.return_value = existing_source

        await service.delete(source_id)

        mock_order_source_repo.find_by_id.assert_called_once_with(source_id)
        mock_order_source_repo.delete.assert_called_once_with(existing_source)

    @pytest.mark.asyncio
    async def test_delete_order_source_not_found(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """存在しないIDを削除しようとするとNotFoundErrorがraiseされる

        given: 指定IDの受注元が存在しない
        when: deleteメソッドを呼び出す
        then: NotFoundErrorがraiseされる
        """
        mock_order_source_repo.find_by_id.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            await service.delete("non-existent-id")

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# AC-012: OrderSourceServiceが重複code/api_keyを検知しエラーを返す
# ---------------------------------------------------------------------------

class TestOrderSourceServiceDuplicateDetection:
    """AC-012: 重複code/api_key検知テスト"""

    @pytest.fixture
    def mock_order_source_repo(self):
        """モック OrderSourceRepository"""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_order_source_repo):
        """テスト対象のサービスインスタンス"""
        return OrderSourceService(order_source_repo=mock_order_source_repo)

    @pytest.mark.asyncio
    async def test_create_duplicate_code_raises_conflict(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """AC-012: 重複するcodeでcreateするとDuplicateErrorがraiseされる

        given: code="RKSYO"の受注元が既に存在する
        when: 同じcode="RKSYO"でcreateメソッドを呼び出す
        then: DuplicateErrorがraiseされる
        """
        existing_source = _make_order_source(code="RKSYO")
        mock_order_source_repo.find_by_code.return_value = existing_source

        data = OrderSourceCreate(
            code="RKSYO",
            name="重複テスト",
            api_key="different-api-key",
            phone="03-0000-0000",
            postal_code="100-0001",
            address_prefecture="東京都",
            address_city="千代田区",
        )

        with pytest.raises(DuplicateError) as exc_info:
            await service.create(data)

        assert exc_info.value.status_code == 409
        assert "code" in exc_info.value.message.lower() or "RKSYO" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_create_duplicate_api_key_raises_conflict(
        self,
        service: OrderSourceService,
        mock_order_source_repo: AsyncMock,
    ):
        """AC-012: 重複するapi_keyでcreateするとDuplicateErrorがraiseされる

        given: あるapi_keyの受注元が既に存在する
        when: 同じapi_keyでcreateメソッドを呼び出す
        then: DuplicateErrorがraiseされる
        """
        mock_order_source_repo.find_by_code.return_value = None
        existing_source = _make_order_source(api_key="duplicate-api-key")
        mock_order_source_repo.find_by_api_key.return_value = existing_source

        data = OrderSourceCreate(
            code="UNIQUE-CODE",
            name="重複APIキーテスト",
            api_key="duplicate-api-key",
            phone="03-0000-0000",
            postal_code="100-0001",
            address_prefecture="東京都",
            address_city="千代田区",
        )

        with pytest.raises(DuplicateError) as exc_info:
            await service.create(data)

        assert exc_info.value.status_code == 409
        assert "api_key" in exc_info.value.message.lower() or "duplicate-api-key" in exc_info.value.message
