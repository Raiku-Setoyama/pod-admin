"""Tests for order list generator."""

from datetime import datetime

import pytest

from app.utils.order_list_generator import OrderListGenerator, get_product_type_name


class TestOrderListGenerator:
    """Tests for OrderListGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create generator instance."""
        return OrderListGenerator()

    def test_generate_order_list_csv_with_items(self, generator):
        """Test CSV generation with items."""
        items = [
            {
                "ordered_date": datetime(2024, 12, 1, 10, 30, 0),
                "order_number": "2623928",
                "uid": "3765370",
                "product_name": "Tシャツ - XL - 正面 - 白",
                "product_type": "tshirt",
                "quantity": 1,
                "size": "XL",
                "position": "正面",
                "color": "白",
                "cost": 1500,
            },
            {
                "ordered_date": datetime(2024, 12, 1, 11, 0, 0),
                "order_number": "2624714",
                "uid": "3766653",
                "product_name": "Tシャツ - M - 正面 - 白",
                "product_type": "tshirt",
                "quantity": 2,
                "size": "M",
                "position": "正面",
                "color": "白",
                "cost": 1500,
            },
        ]

        result = generator.generate_order_list_csv(items)

        # Should be bytes
        assert isinstance(result, bytes)

        # Decode and check content
        content = result.decode("utf-8-sig")
        lines = [line.strip() for line in content.strip().split("\n")]

        # Check header
        assert lines[0] == "注文日,注文番号,製品番号,商品名,商品種類,原価,個数,シール用テキスト情報"

        # Check first data row
        assert "12月01日" in lines[1]
        assert "2623928" in lines[1]
        assert "3765370" in lines[1]
        assert "Tシャツ - XL - 正面 - 白" in lines[1]  # product_name
        assert "Tシャツ - XL - 正面 - 白" in lines[1]  # product_detail
        assert "1500" in lines[1]  # cost
        assert "【個数】1個" in lines[1]
        assert "_1201" in lines[1]  # MMDD format

        # Check second data row
        assert "12月01日" in lines[2]
        assert "2624714" in lines[2]
        assert "【個数】2個" in lines[2]

    def test_generate_order_list_csv_empty_items(self, generator):
        """Test CSV generation with no items."""
        result = generator.generate_order_list_csv([])

        content = result.decode("utf-8-sig")
        lines = [line.strip() for line in content.strip().split("\n")]

        # Should only have header
        assert len(lines) == 1
        assert lines[0] == "注文日,注文番号,製品番号,商品名,商品種類,原価,個数,シール用テキスト情報"

    def test_generate_order_list_csv_seal_text_format(self, generator):
        """Test seal text format is correct."""
        items = [
            {
                "ordered_date": datetime(2024, 12, 15, 10, 0, 0),
                "order_number": "ORD123",
                "uid": "PROD456",
                "product_name": "Test Product",
                "product_type": "tshirt",
                "quantity": 5,
                "size": "M",
                "position": "正面",
                "color": "白",
                "cost": 1000,
            },
        ]

        result = generator.generate_order_list_csv(items)
        content = result.decode("utf-8-sig")

        # Check seal text format: {商品名}【個数】{個数}個_{注文番号}_{製品番号}_{MMDD}
        expected_seal = "Test Product【個数】5個_ORD123_PROD456_1215"
        assert expected_seal in content

    def test_generate_order_list_csv_date_format(self, generator):
        """Test date format is MM月DD日."""
        items = [
            {
                "ordered_date": datetime(2024, 1, 5, 10, 0, 0),
                "order_number": "ORD001",
                "uid": "PROD001",
                "product_name": "Product",
                "product_type": "tshirt",
                "quantity": 1,
                "size": "M",
                "position": "正面",
                "color": "白",
                "cost": 1000,
            },
        ]

        result = generator.generate_order_list_csv(items)
        content = result.decode("utf-8-sig")

        # Check date format with zero padding
        assert "01月05日" in content

    def test_generate_order_list_csv_utf8_bom(self, generator):
        """Test CSV has UTF-8 BOM for Excel compatibility."""
        items = [
            {
                "ordered_date": datetime(2024, 12, 1, 10, 0, 0),
                "order_number": "ORD001",
                "uid": "PROD001",
                "product_name": "日本語テスト",
                "product_type": "tshirt",
                "quantity": 1,
                "size": "M",
                "position": "正面",
                "color": "白",
                "cost": 1000,
            },
        ]

        result = generator.generate_order_list_csv(items)

        # UTF-8 BOM is 0xEF, 0xBB, 0xBF
        assert result[:3] == b"\xef\xbb\xbf"

    def test_generate_order_list_csv_missing_optional_fields(self, generator):
        """Test CSV generation with missing optional fields."""
        items = [
            {
                "ordered_date": None,
                "order_number": "",
                "uid": "",
                "product_name": "",
                "product_type": "",
                "quantity": 1,
                "size": None,
                "position": None,
                "color": None,
                "cost": 0,
            },
        ]

        result = generator.generate_order_list_csv(items)
        content = result.decode("utf-8-sig")

        # Should still generate CSV without errors
        lines = [line.strip() for line in content.strip().split("\n")]
        assert len(lines) == 2  # Header + 1 data row


class TestGetProductTypeName:
    """Tests for get_product_type_name function."""

    def test_get_product_type_name_tshirt(self):
        """Test tshirt product type name."""
        assert get_product_type_name("tshirt") == "Tシャツ"

    def test_get_product_type_name_mug(self):
        """Test mug product type name."""
        assert get_product_type_name("mug") == "マグカップ"

    def test_get_product_type_name_acrylic_keychain(self):
        """Test acrylic_keychain product type name."""
        assert get_product_type_name("acrylic_keychain") == "アクリルキーホルダー"

    def test_get_product_type_name_acrylic_stand(self):
        """Test acrylic_stand product type name."""
        assert get_product_type_name("acrylic_stand") == "アクリルフィギュア"

    def test_get_product_type_name_sticker(self):
        """Test sticker product type name."""
        assert get_product_type_name("sticker") == "ステッカー"

    def test_get_product_type_name_tote_bag(self):
        """Test tote_bag product type name."""
        assert get_product_type_name("tote_bag") == "トートバッグ"

    def test_get_product_type_name_unknown(self):
        """Test unknown product type returns original value."""
        assert get_product_type_name("unknown_type") == "unknown_type"
