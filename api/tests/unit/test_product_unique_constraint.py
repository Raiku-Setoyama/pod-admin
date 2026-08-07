"""商品マスタ ユニーク制約のユニットテスト

FEAT-0008: 商品マスタ（productsテーブル）に product_type / size / position / color の
4カラム複合ユニーク制約を追加する。

テスト対象:
- Product モデルのユニーク制約定義（コメントとして記載）
- ProductService の重複チェックロジック（create / update）
- ProductRepository の find_duplicate メソッド
- DuplicateProductError 例外
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.product import Product, ProductType
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product_service import ProductService
from app.utils.exceptions import DuplicateProductError


class TestDuplicateProductError:
    """DuplicateProductError 例外のテスト"""

    def test_duplicate_product_error_has_409_status(self) -> None:
        """DuplicateProductError は 409 ステータスコードを持つこと"""
        error = DuplicateProductError(
            product_type="tshirt",
            size="M",
            position="正面",
            color="白",
        )
        assert error.status_code == 409

    def test_duplicate_product_error_has_correct_code(self) -> None:
        """DuplicateProductError は DUPLICATE_PRODUCT コードを持つこと"""
        error = DuplicateProductError(
            product_type="tshirt",
            size="M",
            position="正面",
            color="白",
        )
        assert error.code == "DUPLICATE_PRODUCT"

    def test_duplicate_product_error_message_contains_spec(self) -> None:
        """DuplicateProductError のメッセージに仕様情報が含まれること"""
        error = DuplicateProductError(
            product_type="tshirt",
            size="M",
            position="正面",
            color="白",
        )
        assert "tshirt" in error.message
        assert "M" in error.message
        assert "正面" in error.message
        assert "白" in error.message

    def test_duplicate_product_error_handles_none_values(self) -> None:
        """DuplicateProductError が NULL 値を正しく処理すること"""
        error = DuplicateProductError(
            product_type="acrylic_keychain",
            size="50x50mm",
            position=None,
            color=None,
        )
        assert error.status_code == 409
        assert "acrylic_keychain" in error.message
        assert "50x50mm" in error.message


class TestProductModelConstraint:
    """AC-001: Product モデルのユニーク制約定義テスト"""

    def test_ac001_product_model_has_unique_constraint_comment(self) -> None:
        """AC-001: Product モデルにユニーク制約に関するコメント/定義があること

        given: Product モデルの定義
        when: ソースコードを確認する
        then: ユニーク制約の意図が記載されている
        """
        # The actual unique index is created via Alembic migration.
        # Verify the Product model source contains the constraint comment.
        import inspect
        source = inspect.getsource(Product)
        assert "uq_products_type_size_position_color" in source


class TestProductServiceDuplicateCheck:
    """ProductService の重複チェックロジックのテスト"""

    @pytest.fixture
    def mock_product_repo(self) -> Any:
        """モック ProductRepository"""
        return AsyncMock(spec=ProductRepository)

    @pytest.fixture
    def mock_manufacturer_repo(self) -> Any:
        """モック ManufacturerRepository"""
        repo = AsyncMock()
        # デフォルトで有効なメーカーを返す
        repo.find_by_id.return_value = MagicMock(id="mfr-1")
        return repo

    @pytest.fixture
    def service(self, mock_product_repo: Any, mock_manufacturer_repo: Any) -> Any:
        """ProductService インスタンス"""
        return ProductService(
            product_repo=mock_product_repo,
            manufacturer_repo=mock_manufacturer_repo,
        )

    @pytest.mark.asyncio
    async def test_ac002_create_duplicate_raises_error(
        self, service: Any, mock_product_repo: Any
    ) -> None:
        """AC-002: 同一仕様の商品を新規作成しようとすると重複エラー（409）が返ること

        given: product_type=tshirt, size=M, position=正面, color=白 の商品が既に存在する
        when: 同じ product_type, size, position, color で新規作成を試みる
        then: DuplicateProductError（409 Conflict）が発生する
        """
        # 既存の重複商品を返すようにモック
        existing_product = MagicMock(spec=Product)
        existing_product.id = "existing-id"
        mock_product_repo.find_duplicate.return_value = existing_product

        data = ProductCreate(
            product_type=ProductType.TSHIRT,
            size="M",
            position="正面",
            color="白",
            manufacturer_id="mfr-1",
            cost=870,
            lead_time_days=10,
        )

        with pytest.raises(DuplicateProductError) as exc_info:
            await service.create(data)

        assert exc_info.value.status_code == 409
        mock_product_repo.find_duplicate.assert_called_once_with(
            product_type="tshirt",
            size="M",
            position="正面",
            color="白",
            exclude_id=None,
        )

    @pytest.mark.asyncio
    async def test_ac003_create_different_spec_succeeds(
        self, service: Any, mock_product_repo: Any
    ) -> None:
        """AC-003: 異なる仕様の商品は正常に作成できること

        given: product_type=tshirt, size=M の商品が存在する
        when: product_type=tshirt, size=L で新規作成する
        then: 正常に商品が作成される
        """
        # 重複なしを返す
        mock_product_repo.find_duplicate.return_value = None

        # 作成された商品を返すようにモック
        created_product = MagicMock(spec=Product)
        created_product.id = "new-id"
        created_product.product_type = "tshirt"
        created_product.size = "L"
        created_product.position = "正面"
        created_product.color = "白"
        created_product.manufacturer_id = "mfr-1"
        created_product.cost = 870
        created_product.lead_time_days = 10
        created_product.order_limit = None
        created_product.is_active = True
        created_product.created_at = "2026-01-01T00:00:00"
        created_product.updated_at = "2026-01-01T00:00:00"
        mock_product_repo.create.return_value = created_product

        data = ProductCreate(
            product_type=ProductType.TSHIRT,
            size="L",
            position="正面",
            color="白",
            manufacturer_id="mfr-1",
            cost=870,
            lead_time_days=10,
        )

        result = await service.create(data)
        assert result.id == "new-id"
        assert result.size == "L"

    @pytest.mark.asyncio
    async def test_ac004_create_duplicate_with_null_fields_raises_error(
        self, service: Any, mock_product_repo: Any
    ) -> None:
        """AC-004: position と color が NULL の場合も重複チェックが機能すること

        given: product_type=acrylic_keychain, size=50x50mm, position=NULL, color=NULL の商品が存在する
        when: 同じ仕様（position=NULL, color=NULL）で新規作成を試みる
        then: DuplicateProductError（409 Conflict）が発生する
        """
        existing_product = MagicMock(spec=Product)
        existing_product.id = "existing-id"
        mock_product_repo.find_duplicate.return_value = existing_product

        data = ProductCreate(
            product_type=ProductType.ACRYLIC_KEYCHAIN,
            size="50x50mm",
            position=None,
            color=None,
            manufacturer_id="mfr-1",
            cost=285,
            lead_time_days=10,
        )

        with pytest.raises(DuplicateProductError) as exc_info:
            await service.create(data)

        assert exc_info.value.status_code == 409
        mock_product_repo.find_duplicate.assert_called_once_with(
            product_type="acrylic_keychain",
            size="50x50mm",
            position=None,
            color=None,
            exclude_id=None,
        )

    @pytest.mark.asyncio
    async def test_ac005_update_to_duplicate_raises_error(
        self, service: Any, mock_product_repo: Any
    ) -> None:
        """AC-005: 商品更新時に他の商品と重複する場合はエラーになること

        given:
          商品A: product_type=tshirt, size=M, position=正面, color=白
          商品B: product_type=tshirt, size=L, position=正面, color=白
        when: 商品Bの size を M に更新しようとする
        then: DuplicateProductError（409 Conflict）が発生する
        """
        # 商品Bを返す
        product_b = MagicMock(spec=Product)
        product_b.id = "product-b-id"
        product_b.product_type = "tshirt"
        product_b.size = "L"
        product_b.position = "正面"
        product_b.color = "白"
        mock_product_repo.find_by_id.return_value = product_b

        # 重複あり（商品A）を返す
        product_a = MagicMock(spec=Product)
        product_a.id = "product-a-id"
        mock_product_repo.find_duplicate.return_value = product_a

        update_data = ProductUpdate(size="M")

        with pytest.raises(DuplicateProductError) as exc_info:
            await service.update("product-b-id", update_data)

        assert exc_info.value.status_code == 409
        mock_product_repo.find_duplicate.assert_called_once_with(
            product_type="tshirt",
            size="M",
            position="正面",
            color="白",
            exclude_id="product-b-id",
        )

    @pytest.mark.asyncio
    async def test_ac006_update_self_no_conflict(
        self, service: Any, mock_product_repo: Any
    ) -> None:
        """AC-006: 自分自身との重複は許容されること（更新時）

        given: 商品A: product_type=tshirt, size=M, position=正面, color=白
        when: 商品Aの cost のみを変更する（仕様は同一のまま）
        then: 正常に更新される（自分自身との重複はエラーにならない）
        """
        # 商品Aを返す
        product_a = MagicMock(spec=Product)
        product_a.id = "product-a-id"
        product_a.product_type = "tshirt"
        product_a.size = "M"
        product_a.position = "正面"
        product_a.color = "白"
        product_a.manufacturer_id = "mfr-1"
        product_a.cost = 870
        product_a.lead_time_days = 10
        product_a.order_limit = None
        product_a.is_active = True
        product_a.created_at = "2026-01-01T00:00:00"
        product_a.updated_at = "2026-01-01T00:00:00"
        mock_product_repo.find_by_id.return_value = product_a

        # 重複なし（exclude_id で自分自身を除外するため）
        mock_product_repo.find_duplicate.return_value = None

        # 更新後の商品を返す
        updated_product = MagicMock(spec=Product)
        updated_product.id = "product-a-id"
        updated_product.product_type = "tshirt"
        updated_product.size = "M"
        updated_product.position = "正面"
        updated_product.color = "白"
        updated_product.manufacturer_id = "mfr-1"
        updated_product.cost = 900  # cost のみ変更
        updated_product.lead_time_days = 10
        updated_product.order_limit = None
        updated_product.is_active = True
        updated_product.created_at = "2026-01-01T00:00:00"
        updated_product.updated_at = "2026-01-01T00:00:00"
        mock_product_repo.update.return_value = updated_product

        update_data = ProductUpdate(cost=900)

        # エラーが発生しないこと
        result = await service.update("product-a-id", update_data)
        assert result.cost == 900

        # find_duplicate が exclude_id 付きで呼ばれたこと
        mock_product_repo.find_duplicate.assert_called_once_with(
            product_type="tshirt",
            size="M",
            position="正面",
            color="白",
            exclude_id="product-a-id",
        )


class TestProductRepositoryFindDuplicate:
    """AC-010: ProductRepository の find_duplicate メソッドのテスト"""

    def test_ac010_find_duplicate_method_exists(self) -> None:
        """AC-010: ProductRepository に find_duplicate メソッドが存在すること

        given: ProductRepository クラス
        when: find_duplicate メソッドを確認する
        then: メソッドが存在する
        """
        assert hasattr(ProductRepository, "find_duplicate"), (
            "ProductRepository に find_duplicate メソッドが存在しません"
        )

    def test_ac010_find_duplicate_method_is_async(self) -> None:
        """AC-010: find_duplicate メソッドが非同期であること"""
        import asyncio
        assert asyncio.iscoroutinefunction(ProductRepository.find_duplicate), (
            "find_duplicate メソッドは非同期関数であるべきです"
        )

    def test_ac010_find_duplicate_accepts_required_params(self) -> None:
        """AC-010: find_duplicate メソッドが必要なパラメータを受け付けること"""
        import inspect
        sig = inspect.signature(ProductRepository.find_duplicate)
        params = list(sig.parameters.keys())
        assert "product_type" in params
        assert "size" in params
        assert "position" in params
        assert "color" in params
        assert "exclude_id" in params


class TestAlembicMigration:
    """AC-009: Alembicマイグレーションファイルのテスト"""

    def test_ac009_migration_file_exists(self) -> None:
        """AC-009: マイグレーションファイルが存在すること"""
        from pathlib import Path
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "add_product_unique_constraint.py"
        assert migration_path.exists(), (
            f"マイグレーションファイルが見つかりません: {migration_path}"
        )

    def test_ac009_migration_has_correct_revision(self) -> None:
        """AC-009: マイグレーションのリビジョンIDが正しいこと"""
        import importlib.util
        from pathlib import Path

        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "add_product_unique_constraint.py"
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == "add_product_uq_001"
        assert module.down_revision == "migrate_order_source_fk"

    def test_ac009_migration_has_upgrade_function(self) -> None:
        """AC-009: マイグレーションに upgrade 関数が存在すること"""
        import importlib.util
        from pathlib import Path

        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "add_product_unique_constraint.py"
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "upgrade")
        assert callable(module.upgrade)

    def test_ac009_migration_has_downgrade_function(self) -> None:
        """AC-009: マイグレーションに downgrade 関数が存在すること"""
        import importlib.util
        from pathlib import Path

        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "add_product_unique_constraint.py"
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "downgrade")
        assert callable(module.downgrade)
