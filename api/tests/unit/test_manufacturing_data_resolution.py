"""製造データの元画像の解像度の区分（#190）.

DTF 版の元画像の実寸解像度（source_dpi）を、設定の閾値で low / upscaled / ok に分けて
API のレスポンスに出す。管理画面は閾値を持たず、この区分をそのまま表示する。
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.config import settings
from app.schemas.manufacturing_data import (
    ManufacturingDataDetailResponse,
    ManufacturingDataResponse,
    classify_resolution,
)


def _row(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    row: dict[str, Any] = {
        "id": "md-1",
        "product_code": "RKSYO-T",
        "product_type": "tshirt",
        "size": "XL",
        "variant": "dtf",
        "status": "ready",
        "attempts": 1,
        "created_at": now,
        "updated_at": now,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("dpi", "expected"),
    [
        (101.7, "low"),
        (149.9, "low"),
        (150.0, "upscaled"),
        (299.9, "upscaled"),
        (300.0, "ok"),
        (600.0, "ok"),
        (None, None),
    ],
)
def test_classify_resolution_boundaries(dpi: float | None, expected: str | None) -> None:
    assert classify_resolution(dpi) == expected


def test_thresholds_follow_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """閾値を設定で変えると区分が変わる."""
    monkeypatch.setattr(settings, "MFG_RESOLUTION_WARN_DPI", 100.0)
    monkeypatch.setattr(settings, "MFG_RESOLUTION_TARGET_DPI", 120.0)
    assert classify_resolution(99.9) == "low"
    assert classify_resolution(101.7) == "upscaled"
    assert classify_resolution(121.0) == "ok"


def test_list_item_response_includes_resolution_level() -> None:
    dumped = ManufacturingDataResponse.model_validate(_row(source_dpi=121.0)).model_dump()
    assert dumped["source_dpi"] == 121.0
    assert dumped["resolution_level"] == "low"


def test_response_without_record_has_no_level() -> None:
    """インクジェット版・アクリル系・過去のデータは記録が無く、区分も null."""
    dumped = ManufacturingDataResponse.model_validate(
        _row(product_type="acrylic_keychain", variant="clear")
    ).model_dump()
    assert dumped["source_dpi"] is None
    assert dumped["resolution_level"] is None


def test_detail_response_survives_revalidation() -> None:
    """FastAPI は response_model で dump → validate し直す。区分を含む dict を通しても崩れない."""
    detail = ManufacturingDataDetailResponse.model_validate(_row(source_dpi=200.0))
    again = ManufacturingDataDetailResponse.model_validate(detail.model_dump())
    assert again.resolution_level == "upscaled"
    assert again.model_dump(mode="json")["resolution_level"] == "upscaled"
