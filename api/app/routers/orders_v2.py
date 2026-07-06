"""v2 order intake router (製造データ生成の元データを受け取る外部注文受付)."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, get_order_service, verify_api_key
from app.schemas.order import OrderResponse
from app.schemas.order_v2 import OrderCreateV2
from app.services.manufacturing_data_service import run_ensure_for_order
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders-v2"])


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order_v2(
    data: OrderCreateV2,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[OrderService, Depends(get_order_service)],
    api_key_info: Annotated[tuple[str, str], Depends(verify_api_key)],
) -> OrderResponse:
    """外部販売サイト(v2)からの注文受付（API Key認証）。

    完成データURLではなく元データ(PNGレイヤー)の source_images ＋ product_code /
    variant を受け取り、Order/OrderItem を作成する。受付後、製造データ生成を
    BackgroundTasks で非同期に起動する（intake HTTP はブロックしない）。
    """
    _, order_source_id = api_key_info
    order = await service.create_v2(data, order_source_id=order_source_id)
    # 製造データ生成タスクは独自セッションで注文を再読込するため、ここで確定させてから起動する
    await session.commit()
    background_tasks.add_task(run_ensure_for_order, order.id)
    return order
