"""Manufacturer daily digest — 日次発注ダイジェストメールの送信バッチ.

外部トリガ（cron / GitHub Actions 等）が高頻度で内部エンドポイントを叩く。
本サービスは「現在 JST が送信時刻以降」かつ「本日未実行」の場合のみ本処理を実行する。

冪等性:
- 全社日次ガード: app_settings の last_run_date を原子的に claim（多重発火でも 1 回だけ）
- メーカー別ウォーターマーク: last_notified_at を送信成功時のみ更新（新規分のみ・二重送信防止）
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.services.manufacturer_notification import (
    DIGEST_ENABLED_KEY,
    DIGEST_LAST_RUN_DATE_KEY,
    DIGEST_SEND_TIME_KEY,
    parse_send_time,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.repositories.app_setting_repository import AppSettingRepository
    from app.repositories.manufacturer_notification_settings_repository import (
        ManufacturerNotificationSettingsRepository,
    )
    from app.repositories.order_repository import OrderRepository
    from app.services.email_service import EmailService

JST = ZoneInfo("Asia/Tokyo")


class ManufacturerDailyDigestService:
    """メーカー別 日次発注ダイジェストの送信判定・集計・送信を行うバッチサービス."""

    def __init__(
        self,
        db: AsyncSession,
        order_repo: OrderRepository,
        notif_repo: ManufacturerNotificationSettingsRepository,
        app_setting_repo: AppSettingRepository,
        email_service: EmailService | None,
    ) -> None:
        self._db = db
        self._order_repo = order_repo
        self._notif_repo = notif_repo
        self._app_setting_repo = app_setting_repo
        self._email_service = email_service

    async def run_daily_digest(
        self,
        *,
        force: bool = False,
        now: datetime | None = None,
    ) -> dict[str, object]:
        """日次ダイジェストの送信判定と送信を行う.

        Args:
            force: True の場合、時刻・日次・マスタスイッチの各ガードを無視して即時送信する
                （手動再実行・テスト用）。
            now: 現在時刻（テスト用に注入可能）。未指定なら現在時刻を用いる。

        Returns:
            実行結果のサマリー dict。
        """
        now_jst = (now or datetime.now(JST)).astimezone(JST)
        today_str = now_jst.date().isoformat()

        if not force:
            skip_reason = await self._check_gates(now_jst, today_str)
            if skip_reason is not None:
                return self._result(ran=False, reason=skip_reason)
            # 日次ガードを確定させ、後続処理が失敗しても本日の再実行はしない
            await self._db.commit()

        sent: list[str] = []
        skipped_zero: list[str] = []
        failed: list[str] = []

        pairs = await self._notif_repo.list_enabled_with_manufacturer()
        for settings, manufacturer in pairs:
            summary = await self._order_repo.get_new_ordered_summary_by_manufacturer(
                manufacturer.id, since=settings.last_notified_at
            )
            item_count = summary["ordered_item_count"]
            if item_count == 0:
                # 新規の発注済みが 0 件のメーカーは送信しない
                skipped_zero.append(manufacturer.id)
                continue

            to_emails = settings.to_emails or (
                [manufacturer.email] if manufacturer.email else []
            )
            if not to_emails:
                failed.append(manufacturer.id)
                continue

            ok = False
            if self._email_service is not None:
                ok = await self._email_service.send_manufacturer_daily_digest(
                    to_emails=to_emails,
                    manufacturer_name=manufacturer.name,
                    item_count=item_count,
                    total_quantity=summary["total_quantity"],
                    cc_emails=settings.cc_emails,
                    sent_date=now_jst.date(),
                )

            if ok:
                # 送信成功時のみウォーターマークを実行時刻へ更新
                await self._notif_repo.update_last_notified_at(settings, now_jst)
                sent.append(manufacturer.id)
            else:
                failed.append(manufacturer.id)

        await self._db.commit()
        return self._result(
            ran=True,
            reason="ok",
            run_date=today_str,
            sent=sent,
            skipped_zero=skipped_zero,
            failed=failed,
        )

    async def _check_gates(self, now_jst: datetime, today_str: str) -> str | None:
        """送信可否のガードを判定する。スキップすべき理由を返す（送信可なら None）.

        通過した場合、副作用として本日分の日次ガードを claim 済みにする。
        """
        # マスタスイッチ
        enabled = await self._app_setting_repo.find_by_key(DIGEST_ENABLED_KEY)
        if enabled is None or enabled.value != "true":
            return "disabled"

        # 送信時刻ガード（現在 JST が送信時刻以降か）
        send_time_setting = await self._app_setting_repo.find_by_key(DIGEST_SEND_TIME_KEY)
        if send_time_setting is None or not send_time_setting.value:
            return "send_time_not_set"
        if now_jst.time() < parse_send_time(send_time_setting.value):
            return "before_send_time"

        # 日次ガード（本日実行済みならスキップ）: 原子的 claim
        claimed = await self._app_setting_repo.claim_daily_run(
            DIGEST_LAST_RUN_DATE_KEY, today_str
        )
        if not claimed:
            return "already_ran_today"

        return None

    @staticmethod
    def _result(
        *,
        ran: bool,
        reason: str,
        run_date: str | None = None,
        sent: list[str] | None = None,
        skipped_zero: list[str] | None = None,
        failed: list[str] | None = None,
    ) -> dict[str, object]:
        sent = sent or []
        skipped_zero = skipped_zero or []
        failed = failed or []
        return {
            "ran": ran,
            "reason": reason,
            "run_date": run_date,
            "sent_count": len(sent),
            "skipped_zero_count": len(skipped_zero),
            "failed_count": len(failed),
            "sent_manufacturer_ids": sent,
            "skipped_zero_manufacturer_ids": skipped_zero,
            "failed_manufacturer_ids": failed,
        }
