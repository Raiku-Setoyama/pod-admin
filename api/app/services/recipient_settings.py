"""通知先・有効/無効の設定値（app_settings）の共通処理.

外部注文の通知（external_order_notification）と、製造データ生成のアラート
（monitoring_alert_notification）が同じ形式（カンマ区切りのアドレス・"true"/"false"）で
宛先を持つので、解釈と検証をここにまとめる。
"""

from __future__ import annotations

from email_validator import EmailNotValidError, validate_email

# recipients は app_settings.value (String(500)) に収める
RECIPIENTS_MAX_LENGTH = 500


def parse_recipients(value: str | None) -> list[str]:
    """カンマ区切り文字列を宛先アドレスのリストへ変換する（空要素は除去）."""
    if not value:
        return []
    return [addr.strip() for addr in value.split(",") if addr.strip()]


def validate_enabled_value(value: str) -> None:
    """通知の有効/無効の設定値（"true" / "false"）を検証する."""
    if value not in ("true", "false"):
        raise ValueError('通知の有効/無効は "true" または "false" で指定してください')


def validate_recipients_value(value: str) -> None:
    """通知先（カンマ区切りのメールアドレス）の設定値を検証する."""
    if len(value) > RECIPIENTS_MAX_LENGTH:
        raise ValueError(
            f"通知先メールアドレスは合計{RECIPIENTS_MAX_LENGTH}文字以内で指定してください"
        )
    for addr in parse_recipients(value):
        try:
            validate_email(addr, check_deliverability=False)
        except EmailNotValidError:
            raise ValueError(f"メールアドレスの形式が正しくありません: {addr}") from None
