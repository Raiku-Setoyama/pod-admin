"""Internal API router (protected by a shared secret).

外部トリガ（ホスティングの cron / GitHub Actions 等）から叩くための内部エンドポイント。
共有シークレット（X-Internal-Secret）で保護する。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import (
    get_manufacturer_daily_digest_service,
    verify_internal_secret,
)
from app.services.manufacturer_daily_digest import ManufacturerDailyDigestService

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/manufacturer-daily-digest")
async def run_manufacturer_daily_digest(
    service: Annotated[
        ManufacturerDailyDigestService, Depends(get_manufacturer_daily_digest_service)
    ],
    _: Annotated[None, Depends(verify_internal_secret)],
    force: bool = False,
) -> dict[str, object]:
    """メーカー日次発注ダイジェストの送信判定・送信を実行する.

    外部トリガが高頻度（例: 5〜15 分毎）で叩く。現在 JST が設定時刻以降かつ
    本日未実行の場合のみ本処理を実行し、通知 ON かつ新規発注済み ≥ 1 件の
    メーカーへメールを送る。多重発火でも日次ガードと per-manufacturer の
    ウォーターマークにより二重送信しない。

    Args:
        force: True で時刻・日次・マスタスイッチの各ガードを無視して即時送信
            （手動再実行・テスト用）。
    """
    return await service.run_daily_digest(force=force)
