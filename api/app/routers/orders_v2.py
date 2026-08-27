"""Orders v2 router.

外部販売サイトからの注文受付（v2 / 製造データ生成方式）。
完成デザインではなく元データ（PNGレイヤーURL）を受け取り、着信後に illustrator-vm で
製造データを生成する（同一商品はキャッシュ再利用）。

既存の POST /api/v1/orders（design_image_url 方式）は一切変更しない。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import (
    get_external_order_notification_service,
    get_manufacturing_data_service,
    get_order_service,
    verify_api_key,
)
from app.schemas.order import OrderCreateV2, OrderResponse
from app.services.external_order_notification import ExternalOrderNotificationService
from app.services.manufacturing_data_service import ManufacturingDataService
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders-v2"])


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order_v2(
    data: OrderCreateV2,
    order_service: Annotated[OrderService, Depends(get_order_service)],
    md_service: Annotated[ManufacturingDataService, Depends(get_manufacturing_data_service)],
    notification_service: Annotated[
        ExternalOrderNotificationService, Depends(get_external_order_notification_service)
    ],
    api_key_info: Annotated[tuple[str, str], Depends(verify_api_key)],
) -> OrderResponse:
    """Create a new order from external sales site (v2 / manufacturing-data generation).

    Request body (JSON):
    {
        "order_number": "0000001",
        "customer": {...},
        "items": [
            {
                "uid": "0000011",
                "product_type": "acrylic_keychain",
                "product_name": "アクリルキーホルダー デザインA",
                "price": 1200,
                "quantity": 1,
                "size": "50x50mm",
                "color": "アクリル",
                "product_code": "RKSYO-AKC-001",
                "source_images": [
                    {"layer_type": "color", "url": "https://.../color.png"},
                    {"layer_type": "cutline", "url": "https://.../cutline.png"}
                ],
                "thumbnail_image_url": "https://.../thumb.png"
            }
        ]
    }
    """
    _, order_source_id = api_key_info
    order = await order_service.create_v2(data, order_source_id=order_source_id)

    # 製造データ行はここで同期的に紐付ける（発注ゲートを確実に効かせるため）。
    # 生成そのものは行わない。行は pending のまま残り、ワーカー（app/worker.py）が拾う。
    await md_service.prepare_for_order(order.id)

    # 受注通知メール（有効時のみ。レスポンスを返す前に送信する）
    await notification_service.notify_if_enabled(order=order)
    return order
