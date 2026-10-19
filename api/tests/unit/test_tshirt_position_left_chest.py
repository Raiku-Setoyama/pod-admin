"""Tシャツの印刷位置「左胸」（REQ-0070）.

options と受注バリデーションは TshirtPosition enum 由来なので、enum に足せば両方に出る。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.product import ProductType
from app.schemas.external import PriceCalculationRequest
from app.services.external_service import ExternalService
from app.services.order_service import OrderService
from app.utils.exceptions import ValidationError


def _external() -> ExternalService:
    return ExternalService(MagicMock(), MagicMock())


def test_product_options_list_front_and_left_chest() -> None:
    options = _external().get_product_options(ProductType.TSHIRT)
    assert options.position == ["正面", "左胸"]


async def test_price_calculation_is_the_same_for_front_and_left_chest() -> None:
    def req(position: str) -> PriceCalculationRequest:
        return PriceCalculationRequest(
            product_type=ProductType.TSHIRT, size="M", color="白", position=position, quantity=1
        )

    svc = _external()
    front = await svc._calculate_tshirt_price(req("正面"))
    left = await svc._calculate_tshirt_price(req("左胸"))
    assert left.unit_price == front.unit_price
    assert left.position == "左胸"


async def test_price_calculation_rejects_unknown_position() -> None:
    data = PriceCalculationRequest(
        product_type=ProductType.TSHIRT, size="M", color="白", position="背面", quantity=1
    )
    with pytest.raises(ValidationError, match="左胸"):
        await _external()._calculate_tshirt_price(data)


@pytest.mark.parametrize("position", ["正面", "左胸"])
def test_order_intake_accepts_left_chest(position: str) -> None:
    item = SimpleNamespace(uid="u1", size="L", color="白", position=position)
    OrderService._validate_tshirt_attributes(MagicMock(), item)  # 例外が出なければよい


def test_order_intake_rejects_unknown_position() -> None:
    item = SimpleNamespace(uid="u1", size="L", color="白", position="背面")
    with pytest.raises(ValidationError, match="左胸"):
        OrderService._validate_tshirt_attributes(MagicMock(), item)
