"""ステッカー「クリア」カラー削除のユニットテスト

FEAT-0007: ステッカー商品タイプから「クリア」カラーを削除し、
「ホワイト」のみの単一カラー体制にする。

テスト対象:
- StickerColor Enum
- ExternalService.get_product_options (STICKER)
- ExternalService.calculate_price (STICKER)
- STICKER_PRICES 辞書
"""

import pytest
from unittest.mock import AsyncMock

from app.models.order import StickerColor
from app.models.product import ProductType
from app.schemas.external import PriceCalculationRequest
from app.services.external_service import ExternalService, STICKER_PRICES
from app.utils.exceptions import ValidationError


class TestStickerColorEnum:
    """StickerColor Enum のテスト"""

    def test_ac001_sticker_color_has_no_clear(self):
        """AC-001: StickerColor Enum に「クリア」が存在しないこと

        given: StickerColor Enum の定義
        when: StickerColor のメンバーを列挙する
        then: WHITE のみが存在し、CLEAR は存在しない
        """
        member_names = [member.name for member in StickerColor]
        assert "CLEAR" not in member_names, (
            "StickerColor に CLEAR メンバーが存在します。削除が必要です。"
        )

    def test_ac001_sticker_color_has_only_white(self):
        """AC-001: StickerColor Enum に WHITE のみが存在すること

        given: StickerColor Enum の定義
        when: StickerColor のメンバーを列挙する
        then: WHITE のみが存在する
        """
        member_names = [member.name for member in StickerColor]
        assert member_names == ["WHITE"], (
            f"StickerColor のメンバーは WHITE のみであるべきですが、{member_names} が存在します。"
        )

    def test_ac001_sticker_color_clear_value_is_not_valid(self):
        """AC-001: StickerColor Enum に「クリア」値が存在しないこと

        given: StickerColor Enum の定義
        when: 「クリア」値でEnumを生成しようとする
        then: ValueError が発生する
        """
        with pytest.raises(ValueError):
            StickerColor("クリア")

    def test_ac001_sticker_color_white_value_is_valid(self):
        """AC-001: StickerColor Enum に「ホワイト」値が有効であること

        given: StickerColor Enum の定義
        when: 「ホワイト」値でEnumを生成する
        then: 正常に生成される
        """
        color = StickerColor("ホワイト")
        assert color == StickerColor.WHITE
        assert color.value == "ホワイト"


class TestStickerOrderValidation:
    """ステッカー受注バリデーションのテスト"""

    @pytest.fixture
    def service(self):
        """ExternalService のインスタンス（モック依存）"""
        mock_product_repo = AsyncMock()
        mock_order_repo = AsyncMock()
        return ExternalService(mock_product_repo, mock_order_repo)

    def test_ac002_sticker_validation_rejects_clear_color(self, service: ExternalService):
        """AC-002: ステッカーの受注バリデーションで「クリア」が拒否されること

        given: ステッカー商品の受注データ
        when: color に「クリア」を指定して受注バリデーションを実行する
        then: ValidationError が発生し、有効な色は「ホワイト」のみと示される
        """
        request = PriceCalculationRequest(
            product_type=ProductType.STICKER,
            size="100x100mm",
            color="クリア",
            quantity=1,
        )

        with pytest.raises(ValidationError) as exc_info:
            # calculate_price は同期的にバリデーションを行い、
            # _calculate_sticker_price を呼ぶ（同期メソッド）
            service._calculate_sticker_price(request)

        # エラーメッセージに「ホワイト」が含まれ、有効な色として示されること
        assert "ホワイト" in exc_info.value.message, (
            f"エラーメッセージに「ホワイト」が含まれるべきですが: {exc_info.value.message}"
        )
        # 「クリア」が有効な色として含まれないこと
        assert "クリア" not in exc_info.value.message or "Invalid color 'クリア'" in exc_info.value.message, (
            f"エラーメッセージが不適切です: {exc_info.value.message}"
        )

    def test_ac003_sticker_validation_accepts_white_color(self, service: ExternalService):
        """AC-003: ステッカーの受注バリデーションで「ホワイト」が受け付けられること

        given: ステッカー商品の受注データ
        when: color に「ホワイト」を指定して受注バリデーションを実行する
        then: バリデーションが成功する
        """
        request = PriceCalculationRequest(
            product_type=ProductType.STICKER,
            size="100x100mm",
            color="ホワイト",
            quantity=1,
        )

        # ValidationError が発生しないこと
        result = service._calculate_sticker_price(request)
        assert result.color == "ホワイト"
        assert result.product_type == ProductType.STICKER


class TestStickerProductOptions:
    """ステッカー商品オプション取得のテスト"""

    @pytest.fixture
    def service(self):
        """ExternalService のインスタンス（モック依存）"""
        mock_product_repo = AsyncMock()
        mock_order_repo = AsyncMock()
        return ExternalService(mock_product_repo, mock_order_repo)

    def test_ac004_sticker_options_returns_only_white(self, service: ExternalService):
        """AC-004: ステッカーの商品オプション取得で「ホワイト」のみ返ること

        given: ExternalService の get_product_options
        when: product_type に STICKER を指定する
        then: color リストに「ホワイト」のみが含まれ、「クリア」は含まれない
        """
        result = service.get_product_options(ProductType.STICKER)

        assert result.product_type == ProductType.STICKER
        assert result.color == ["ホワイト"], (
            f"ステッカーのカラーは ['ホワイト'] のみであるべきですが、{result.color} が返されました。"
        )
        assert "クリア" not in result.color, (
            "ステッカーのカラーに「クリア」が含まれています。削除が必要です。"
        )


class TestStickerPriceCalculation:
    """ステッカー価格計算のテスト"""

    @pytest.fixture
    def service(self):
        """ExternalService のインスタンス（モック依存）"""
        mock_product_repo = AsyncMock()
        mock_order_repo = AsyncMock()
        return ExternalService(mock_product_repo, mock_order_repo)

    def test_ac005_sticker_price_rejects_clear_color(self, service: ExternalService):
        """AC-005: ステッカーの価格計算で「クリア」が拒否されること

        given: ExternalService の calculate_price
        when: product_type=sticker, color=クリア で価格計算を実行する
        then: ValidationError が発生する
        """
        request = PriceCalculationRequest(
            product_type=ProductType.STICKER,
            size="100x100mm",
            color="クリア",
            quantity=1,
        )

        with pytest.raises(ValidationError):
            service._calculate_sticker_price(request)

    def test_ac006_sticker_price_succeeds_with_white_at_79_yen(self, service: ExternalService):
        """AC-006: ステッカー100x100mmの価格計算で「ホワイト」が成功すること

        given: ExternalService の calculate_price
        when: product_type=sticker, size=100x100mm, color=ホワイト で価格計算を実行する
        then: 単価79円で価格計算が成功する
        """
        request = PriceCalculationRequest(
            product_type=ProductType.STICKER,
            size="100x100mm",
            color="ホワイト",
            quantity=3,
        )

        result = service._calculate_sticker_price(request)

        assert result.unit_price == 79, (
            f"ステッカー100x100mmの単価は79円であるべきですが、{result.unit_price}円です。"
        )
        assert result.total_price == 79 * 3, (
            f"合計金額は {79 * 3}円であるべきですが、{result.total_price}円です。"
        )
        assert result.quantity == 3

    def test_ac006_sticker_price_50x50mm(self, service: ExternalService):
        """AC-006: ステッカー50x50mmの単品価格が50円であること

        given: ExternalService の calculate_price
        when: product_type=sticker, size=50x50mm, color=ホワイト, quantity=1 で価格計算を実行する
        then: 単価50円、合計50円で成功する
        """
        request = PriceCalculationRequest(
            product_type=ProductType.STICKER,
            size="50x50mm",
            color="ホワイト",
            quantity=1,
        )

        result = service._calculate_sticker_price(request)

        assert result.unit_price == 50
        assert result.total_price == 50


class TestStickerPricesDictionary:
    """STICKER_PRICES 辞書のテスト"""

    def test_ac007_sticker_prices_has_no_clear(self):
        """AC-007: STICKER_PRICES に「クリア」の価格が存在しないこと

        given: STICKER_PRICES 辞書
        when: 辞書のキーを確認する
        then: 「クリア」は存在しない
        """
        assert "クリア" not in STICKER_PRICES, (
            "STICKER_PRICES に「クリア」のエントリが存在します。削除が必要です。"
        )

    def test_ac007_sticker_prices_keyed_by_size(self):
        """AC-007: STICKER_PRICES がサイズベースであること

        given: STICKER_PRICES 辞書
        when: 辞書のキーを確認する
        then: 全サイズのキーが存在する
        """
        assert list(STICKER_PRICES.keys()) == ["50x50mm", "70x70mm", "100x100mm"], (
            f"STICKER_PRICES のキーはサイズベースであるべきですが、"
            f"{list(STICKER_PRICES.keys())} です。"
        )

    def test_ac007_sticker_prices_100x100mm_is_79(self):
        """AC-007: STICKER_PRICES の 100x100mm の価格が79円であること

        given: STICKER_PRICES 辞書
        when: 100x100mm の価格を確認する
        then: 79円である
        """
        assert STICKER_PRICES.get("100x100mm") == 79, (
            f"STICKER_PRICES の 100x100mm の価格は79円であるべきですが、"
            f"{STICKER_PRICES.get('100x100mm')}円です。"
        )
