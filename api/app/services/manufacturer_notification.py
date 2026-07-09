"""Manufacturer notification settings — 設定キー・バリデーション・CRUD サービス.

メーカー別 日次発注ダイジェストメールの設定を扱う。
- 全社共通の設定は app_settings（key-value）で管理する（送信時刻・マスタスイッチ・日次ガード）。
- メーカー別の宛先(To/CC)・ON/OFF は manufacturer_notification_settings テーブルで管理する。
"""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from email_validator import EmailNotValidError, validate_email

from app.schemas.manufacturer_notification import (
    ManufacturerNotificationSettingsResponse,
    ManufacturerNotificationSettingsUpdate,
)
from app.utils.exceptions import AppException, ManufacturerNotFoundError

if TYPE_CHECKING:
    from app.repositories.manufacturer_notification_settings_repository import (
        ManufacturerNotificationSettingsRepository,
    )
    from app.repositories.manufacturer_repository import ManufacturerRepository

# app_settings のキー（全社共通）
DIGEST_ENABLED_KEY = "manufacturer_daily_digest_enabled"
DIGEST_SEND_TIME_KEY = "manufacturer_daily_digest_send_time"
DIGEST_LAST_RUN_DATE_KEY = "manufacturer_daily_digest_last_run_date"

# 宛先の上限（To/CC それぞれ）
MAX_EMAILS = 20


def normalize_emails(emails: list[str]) -> list[str]:
    """前後空白を除去し、空要素を落とし、重複を除いて順序を保つ."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in emails:
        addr = raw.strip()
        if not addr or addr in seen:
            continue
        seen.add(addr)
        result.append(addr)
    return result


def validate_emails(emails: list[str]) -> None:
    """メールアドレスの形式と件数を検証する（不正なら日本語 ValueError）."""
    if len(emails) > MAX_EMAILS:
        raise ValueError(f"メールアドレスは最大{MAX_EMAILS}件まで登録できます")
    for addr in emails:
        try:
            validate_email(addr, check_deliverability=False)
        except EmailNotValidError:
            raise ValueError(f"メールアドレスの形式が正しくありません: {addr}") from None


def parse_send_time(value: str) -> time:
    """"HH:MM" を time に変換する（不正なら日本語 ValueError）."""
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M")
    except ValueError:
        raise ValueError('送信時刻は "HH:MM"（24時間表記）で指定してください') from None
    return parsed.time()


def validate_digest_setting_value(key: str, value: str) -> None:
    """app_settings（メーカー日次通知）の設定値を検証する.

    ルーターでキャッチして 422 に変換する前提で、日本語メッセージ付きの
    ValueError を送出する。
    """
    if key == DIGEST_ENABLED_KEY:
        if value not in ("true", "false"):
            raise ValueError('通知の有効/無効は "true" または "false" で指定してください')
    elif key == DIGEST_SEND_TIME_KEY:
        parse_send_time(value)


class ManufacturerNotificationService:
    """メーカー別 通知設定の取得・更新（運営ダッシュボード用 CRUD）."""

    def __init__(
        self,
        notif_repo: ManufacturerNotificationSettingsRepository,
        manufacturer_repo: ManufacturerRepository,
    ) -> None:
        self._notif_repo = notif_repo
        self._manufacturer_repo = manufacturer_repo

    async def get_settings(
        self, manufacturer_id: str
    ) -> ManufacturerNotificationSettingsResponse:
        """メーカーの通知設定を取得する（未登録ならデフォルト値を返す）."""
        await self._require_manufacturer(manufacturer_id)
        settings = await self._notif_repo.find_by_manufacturer_id(manufacturer_id)
        if settings is None:
            return ManufacturerNotificationSettingsResponse(
                manufacturer_id=manufacturer_id,
                daily_digest_enabled=False,
                to_emails=[],
                cc_emails=[],
                last_notified_at=None,
            )
        return ManufacturerNotificationSettingsResponse.model_validate(settings)

    async def update_settings(
        self,
        manufacturer_id: str,
        data: ManufacturerNotificationSettingsUpdate,
    ) -> ManufacturerNotificationSettingsResponse:
        """メーカーの通知設定を更新する（last_notified_at は保持）."""
        await self._require_manufacturer(manufacturer_id)
        to_emails = normalize_emails(data.to_emails)
        cc_emails = normalize_emails(data.cc_emails)
        try:
            validate_emails(to_emails)
            validate_emails(cc_emails)
        except ValueError as e:
            raise AppException(422, "VALIDATION_ERROR", str(e)) from None
        settings = await self._notif_repo.upsert(
            manufacturer_id,
            daily_digest_enabled=data.daily_digest_enabled,
            to_emails=to_emails,
            cc_emails=cc_emails,
        )
        return ManufacturerNotificationSettingsResponse.model_validate(settings)

    async def _require_manufacturer(self, manufacturer_id: str) -> None:
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if manufacturer is None:
            raise ManufacturerNotFoundError(manufacturer_id)
