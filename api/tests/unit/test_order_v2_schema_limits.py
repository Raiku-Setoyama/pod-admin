"""Unit tests for v2 order schema DoS guards (list length caps)."""

import pytest
from pydantic import ValidationError

from app.schemas.order import OrderCreateV2, OrderItemCreateV2

_CUSTOMER = {
    "name": "検証",
    "postal_code": "150-0001",
    "address_prefecture": "東京都",
    "address_city": "渋谷区1-1",
    "phone": "090-0000-0000",
}


def _layer(i):
    return {"layer_type": "color", "url": f"https://cdn.trusted/{i}.png"}


def _item(uid="9000011", n_layers=2):
    return {
        "uid": uid,
        "product_type": "acrylic_keychain",
        "product_name": "x",
        "price": 100,
        "quantity": 1,
        "size": "50x50mm",
        "product_code": "RKSYO-1",
        "source_images": [_layer(i) for i in range(n_layers)],
    }


class TestSourceImagesCap:
    def test_accepts_reasonable_layer_count(self):
        OrderItemCreateV2.model_validate(_item(n_layers=4))

    def test_rejects_too_many_source_images(self):
        with pytest.raises(ValidationError):
            OrderItemCreateV2.model_validate(_item(n_layers=50))


class TestItemsCap:
    def test_rejects_too_many_items(self):
        payload = {
            "order_number": "0000001",
            "customer": _CUSTOMER,
            "items": [_item(uid=f"{9000000 + i:07d}") for i in range(200)],
        }
        with pytest.raises(ValidationError):
            OrderCreateV2.model_validate(payload)
