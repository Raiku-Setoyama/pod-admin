"""Regression: manufacturer order item responses must tolerate NULL 納品予定日.

`expected_delivery_date` is nullable in the DB (order_items). A single item with a
NULL value must not 500 the whole manufacturer-order endpoint.
"""

from datetime import UTC, datetime

from app.schemas.manufacturer import (
    AllManufacturerOrderItemResponse,
    ManufacturerOrderItemResponse,
)

_COMMON = {
    "id": "i1",
    "order_id": "o1",
    "order_number": "0000001",
    "uid": "0000011",
    "product_id": "p1",
    "product_name": "x",
    "product_type": "acrylic_keychain",
    "price": 100,
    "quantity": 1,
    "size": "50x50mm",
    "position": None,
    "color": "アクリル",
    "design_image_url": None,
    "thumbnail_image_url": None,
    "ordered_at": datetime.now(UTC),
    "customer_name": "c",
    "status": "ordered",
    "lead_time_days": 10,
    "expected_delivery_date": None,
}


def test_manufacturer_order_item_allows_null_delivery_date() -> None:
    resp = ManufacturerOrderItemResponse(**_COMMON)
    assert resp.expected_delivery_date is None


def test_all_manufacturer_order_item_allows_null_delivery_date() -> None:
    resp = AllManufacturerOrderItemResponse(
        **_COMMON, manufacturer_id="m1", manufacturer_name="M"
    )
    assert resp.expected_delivery_date is None
