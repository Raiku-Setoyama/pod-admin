"""Manufacturer notification settings schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ManufacturerNotificationSettingsResponse(BaseModel):
    """メーカー別 通知設定レスポンス."""

    model_config = ConfigDict(from_attributes=True)

    manufacturer_id: str
    daily_digest_enabled: bool
    # To 未設定時は送信側で manufacturer.email をデフォルトにする
    to_emails: list[str]
    cc_emails: list[str]
    last_notified_at: datetime | None = None


class ManufacturerNotificationSettingsUpdate(BaseModel):
    """メーカー別 通知設定 更新リクエスト.

    メールアドレスの形式・件数はサービス層で検証し、日本語メッセージ付きの
    422 を返す（フロントの共通エラー envelope に乗せるため）。
    """

    daily_digest_enabled: bool = False
    to_emails: list[str] = Field(default_factory=list)
    cc_emails: list[str] = Field(default_factory=list)
