"""External order notification service.

外部販売サイト経由で注文を受け付けた際に、社内担当者へ受注通知メールを送る。
通知先・有効/無効は app_settings（key-value）で管理する。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from email_validator import EmailNotValidError, validate_email

if TYPE_CHECKING:
    from app.repositories.app_setting_repository import AppSettingRepository
    from app.schemas.order import OrderResponse
    from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

# app_settings のキー
NOTIFICATION_ENABLED_KEY = "external_order_notification_enabled"
NOTIFICATION_RECIPIENTS_KEY = "external_order_notification_recipients"

# recipients は app_settings.value (String(500)) に収める
RECIPIENTS_MAX_LENGTH = 500


def parse_recipients(value: str | None) -> list[str]:
    """カンマ区切り文字列を宛先アドレスのリストへ変換する（空要素は除去）."""
    if not value:
        return []
    return [addr.strip() for addr in value.split(",") if addr.strip()]


def validate_setting_value(key: str, value: str) -> None:
    """外部注文通知の設定値を検証する.

    不正な場合は日本語メッセージ付きの ValueError を送出する。
    呼び出し側（ルーター）でキャッチして 422 に変換する。
    """
    if key == NOTIFICATION_ENABLED_KEY:
        if value not in ("true", "false"):
            raise ValueError('通知の有効/無効は "true" または "false" で指定してください')
    elif key == NOTIFICATION_RECIPIENTS_KEY:
        if len(value) > RECIPIENTS_MAX_LENGTH:
            raise ValueError(
                f"通知先メールアドレスは合計{RECIPIENTS_MAX_LENGTH}文字以内で指定してください"
            )
        for addr in parse_recipients(value):
            try:
                validate_email(addr, check_deliverability=False)
            except EmailNotValidError:
                raise ValueError(
                    f"メールアドレスの形式が正しくありません: {addr}"
                ) from None


class ExternalOrderNotificationService:
    """確定済みの外部注文をもとに、受注通知メールを送信するサービス."""

    def __init__(
        self,
        app_setting_repo: AppSettingRepository,
        email_service: EmailService | None,
    ) -> None:
        self._app_setting_repo = app_setting_repo
        self._email_service = email_service

    async def notify_if_enabled(self, *, order: OrderResponse) -> None:
        """通知が有効かつ宛先がある場合に、受注通知メールを送信する.

        レスポンスを返す前に送信する。コンテナ実行基盤ではレスポンス送出後に CPU が
        絞られ、そこに積んだ処理は完走しないため、送信を後ろに回せない（ADR-0026）。
        SendGrid への 1 往復ぶん外部APIのレイテンシが増える。

        設定読込や送信で例外が起きても、注文受付（API レスポンス）は絶対に失敗させない
        （メール障害で業務処理を止めない。ADR-0014）。
        """
        try:
            if self._email_service is None:
                return

            enabled = await self._app_setting_repo.find_by_key(NOTIFICATION_ENABLED_KEY)
            if enabled is None or enabled.value != "true":
                return

            recipients_setting = await self._app_setting_repo.find_by_key(
                NOTIFICATION_RECIPIENTS_KEY
            )
            recipients = parse_recipients(
                recipients_setting.value if recipients_setting else None
            )
            if not recipients:
                return

            await self._email_service.send_external_order_notification(
                to_emails=recipients,
                order_number=order.order_number,
                source_code=order.source,
                ordered_at=order.ordered_at,
                customer_name=order.customer_name or "",
                order_items=[
                    {"product_name": item.product_name, "quantity": item.quantity}
                    for item in order.items
                ],
                total_price=order.total_price,
                order_id=order.id,
            )
            logger.info(
                "Sent external order notification for order %s to %d recipient(s)",
                order.order_number,
                len(recipients),
            )
        except Exception:
            # 通知のための処理は注文受付を失敗させてはならない
            logger.exception(
                "Failed to send external order notification for order %s",
                order.order_number,
            )
