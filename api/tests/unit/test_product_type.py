"""ProductType Enumのテスト

FEAT-0002: 商品種別を5種類に限定（マグカップ削除）

このテストは、ProductType Enum に許可された5種類のみが含まれ、
MUG が削除されていることを検証します。
"""

import pytest

from app.models.product import ProductType


class TestProductType:
    """ProductType Enumのテスト"""

    def test_product_type_has_exactly_five_types(self):
        """ProductTypeは正確に5種類のみ定義されている"""
        expected_count = 5
        actual_count = len(ProductType)

        assert actual_count == expected_count, (
            f"ProductType should have exactly {expected_count} types, "
            f"but has {actual_count}"
        )

    def test_product_type_contains_acrylic_keychain(self):
        """ProductTypeにアクリルキーホルダーが含まれる"""
        assert ProductType.ACRYLIC_KEYCHAIN.value == "acrylic_keychain"

    def test_product_type_contains_acrylic_stand(self):
        """ProductTypeにアクリルスタンドが含まれる"""
        assert ProductType.ACRYLIC_STAND.value == "acrylic_stand"

    def test_product_type_contains_sticker(self):
        """ProductTypeにステッカーが含まれる"""
        assert ProductType.STICKER.value == "sticker"

    def test_product_type_contains_tote_bag(self):
        """ProductTypeにトートバッグが含まれる"""
        assert ProductType.TOTE_BAG.value == "tote_bag"

    def test_product_type_contains_tshirt(self):
        """ProductTypeにTシャツが含まれる"""
        assert ProductType.TSHIRT.value == "tshirt"

    def test_product_type_does_not_contain_mug(self):
        """ProductTypeにマグカップ（MUG）が含まれない"""
        # MUGが存在しないことを確認
        assert not hasattr(ProductType, "MUG"), (
            "ProductType should not have MUG attribute"
        )

        # 値のリストに "mug" が含まれないことを確認
        values = [member.value for member in ProductType]
        assert "mug" not in values, (
            "ProductType should not contain 'mug' value"
        )

    def test_all_allowed_product_types(self):
        """許可された5種類の商品種別がすべて存在する"""
        allowed_values = {
            "acrylic_keychain",
            "acrylic_stand",
            "sticker",
            "tote_bag",
            "tshirt",
        }
        actual_values = {member.value for member in ProductType}

        assert actual_values == allowed_values, (
            f"ProductType should contain exactly {allowed_values}, "
            f"but contains {actual_values}"
        )
