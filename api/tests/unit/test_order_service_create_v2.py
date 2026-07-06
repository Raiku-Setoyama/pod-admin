"""Unit tests for OrderService.create_v2 (v2 intake field persistence + validation)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.order_v2 import OrderCreateV2
from app.services.order_service import OrderService
from app.utils.exceptions import DuplicateError, ValidationError


def _service():
    order_repo = AsyncMock()
    product_repo = AsyncMock()
    shipment_repo = AsyncMock()
    service = OrderService(order_repo, product_repo, shipment_repo)
    # _to_response は別テスト対象なので固定値でバイパス
    service._to_response = AsyncMock(return_value=MagicMock())
    return service, order_repo, product_repo


def _customer():
    return {
        "name": "山田太郎",
        "postal_code": "100-0001",
        "address_prefecture": "東京都",
        "address_city": "千代田区1-1",
        "phone": "090-0000-0000",
    }


def _keychain_payload(**item_overrides):
    item = {
        "uid": "0000001",
        "product_type": "acrylic_keychain",
        "product_name": "キーホルダー",
        "price": 1000,
        "quantity": 1,
        "size": "50x50mm",
        "variant": "clear",
        "product_code": "PC-1",
        "source_images": [
            {"layer_type": "color", "url": "http://x/c.png"},
            {"layer_type": "cutline", "url": "http://x/l.png"},
        ],
    }
    item.update(item_overrides)
    return OrderCreateV2(order_number="0000001", customer=_customer(), items=[item])


class TestCreateV2:
    @pytest.mark.asyncio
    async def test_persists_v2_fields_on_order_item(self):
        service, order_repo, product_repo = _service()
        order_repo.find_by_order_number.return_value = None
        product_repo.find_by_product_type.return_value = MagicMock(id="prod-1", lead_time_days=3)
        order_repo.create.side_effect = lambda order: order  # echo the built order

        await service.create_v2(_keychain_payload(), order_source_id="src-1")

        order_repo.create.assert_awaited_once()
        built_order = order_repo.create.call_args.args[0]
        item = built_order.items[0]
        assert item.product_code == "PC-1"
        assert item.variant == "clear"
        assert item.source_images == [
            {"layer_type": "color", "url": "http://x/c.png"},
            {"layer_type": "cutline", "url": "http://x/l.png"},
        ]
        assert built_order.order_source_id == "src-1"

    @pytest.mark.asyncio
    async def test_stand_variant_normalized_to_none(self):
        service, order_repo, product_repo = _service()
        order_repo.find_by_order_number.return_value = None
        product_repo.find_by_product_type.return_value = MagicMock(id="prod-1", lead_time_days=3)
        order_repo.create.side_effect = lambda order: order
        # acrylic_stand はバリアントなし: variant を送っても None に正規化される
        payload = OrderCreateV2(
            order_number="0000002",
            customer=_customer(),
            items=[
                {
                    "uid": "0000002",
                    "product_type": "acrylic_stand",
                    "product_name": "スタンド",
                    "price": 1500,
                    "quantity": 1,
                    "size": "70x70mm",
                    "variant": "clear",
                    "product_code": "PC-STAND",
                    "source_images": [
                        {"layer_type": "color", "url": "http://x/c.png"},
                        {"layer_type": "cutline", "url": "http://x/l.png"},
                    ],
                }
            ],
        )
        await service.create_v2(payload, order_source_id="src-1")
        item = order_repo.create.call_args.args[0].items[0]
        assert item.variant is None

    @pytest.mark.asyncio
    async def test_invalid_item_missing_variant_raises(self):
        service, order_repo, product_repo = _service()
        order_repo.find_by_order_number.return_value = None
        # keychain で variant 未指定 → mfg_product_mapping 検証で ValidationError
        with pytest.raises(ValidationError):
            await service.create_v2(_keychain_payload(variant=None), order_source_id="src-1")
        order_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_duplicate_order_number_raises(self):
        service, order_repo, product_repo = _service()
        order_repo.find_by_order_number.return_value = MagicMock()  # 既存注文あり
        with pytest.raises(DuplicateError):
            await service.create_v2(_keychain_payload(), order_source_id="src-1")
        order_repo.create.assert_not_awaited()
