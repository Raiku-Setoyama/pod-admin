"""Internal API router (protected by a shared secret).

外部トリガ（ホスティングの cron / GitHub Actions 等）から叩くための内部エンドポイント。
共有シークレット（X-Internal-Secret）で保護する。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import (
    get_manufacturer_daily_digest_service,
    get_monitoring_alert_notification_service,
    verify_internal_basic_auth,
    verify_internal_secret,
)
from app.schemas.monitoring_alert import MonitoringWebhookPayload
from app.services.manufacturer_daily_digest import ManufacturerDailyDigestService
from app.services.monitoring_alert_notification import (
    AlertDelivery,
    MonitoringAlertNotificationService,
)
from app.utils.exceptions import AppException

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


# 認証を先に通す（未認証のリクエストで DB セッションやメール送信の準備をしない）
@router.post("/monitoring-alerts", dependencies=[Depends(verify_internal_basic_auth)])
async def receive_monitoring_alert(
    payload: MonitoringWebhookPayload,
    service: Annotated[
        MonitoringAlertNotificationService, Depends(get_monitoring_alert_notification_service)
    ],
) -> dict[str, str]:
    """Cloud Monitoring のアラート（Webhook）を受け、管理画面で設定した宛先へメールで送る.

    宛先の設定は管理画面「設定 → 製造データ生成のアラート」（app_settings）。
    送れなかったときは 503 を返す（Monitoring に失敗として残す）。宛先が無い・無効に
    しているのは設定どおりの結果なので 200 を返す。
    """
    delivery = await service.notify(payload.incident)
    if delivery in (AlertDelivery.SEND_FAILED, AlertDelivery.EMAIL_NOT_CONFIGURED):
        raise AppException(503, "ALERT_NOT_DELIVERED", f"alert was not delivered: {delivery.value}")
    return {"delivery": delivery.value}
