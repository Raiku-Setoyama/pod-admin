"""注文〆切時間（order deadline time）サービス.

外部販売サイトから注文を受け付けた際の「実効受注日（起算日）」を、管理者が
設定できる「注文〆切時間」に基づいて算出する。〆切時刻以降(JST)に着信した注文は
当日分のメーカー発注に間に合わないため、起算日を翌営業日へ繰り下げ、納品予定日・
配送予定日を実態に沿った日付にする。

設定は app_settings（key-value）の order_deadline_time（"HH:MM"・JST・24h、
空文字は無効）で管理する。external_order_notification.py の *_KEY 定数＋
validate_setting_value の流儀に合わせている。
"""

from __future__ import annotations

import datetime as dt
import re

from app.repositories.app_setting_repository import AppSettingRepository
from app.utils.business_day_calculator import next_business_day

# app_settings のキー
ORDER_DEADLINE_TIME_KEY = "order_deadline_time"

# "HH:MM"（00:00〜23:59・24時間表記・ゼロ埋め必須）を厳密に検証する
_DEADLINE_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_deadline_time(value: str | None) -> dt.time | None:
    """"HH:MM" 文字列を time へ変換する.

    空文字・未設定・不正な形式はすべて None（＝〆切無効）として扱う。
    保存時に validate_setting_value で弾いているため通常は正しい値のみ届くが、
    万一不正値が残っていても後方互換（当日起算）となるよう防御的に None を返す。
    """
    if not value:
        return None
    match = _DEADLINE_TIME_PATTERN.match(value.strip())
    if not match:
        return None
    return dt.time(int(match.group(1)), int(match.group(2)))


async def get_deadline_time(setting_repo: AppSettingRepository) -> dt.time | None:
    """app_settings から注文〆切時刻を読み込む（未設定・不正値は None＝無効）.

    get_shipping_preparation_days と同じく、リポジトリ読込＋パースを1箇所に隠蔽する。
    """
    setting = await setting_repo.find_by_key(ORDER_DEADLINE_TIME_KEY)
    return parse_deadline_time(setting.value if setting else None)


def validate_setting_value(value: str) -> None:
    """注文〆切時間の設定値を検証する.

    空文字（無効化）は許可し、それ以外は "HH:MM"（00:00〜23:59）のみ許可する。
    不正な場合は日本語メッセージ付きの ValueError を送出する。呼び出し側
    （ルーター）でキャッチして 422 に変換する。
    """
    if value == "":
        return
    if not _DEADLINE_TIME_PATTERN.match(value):
        raise ValueError("注文〆切時間は HH:MM 形式（00:00〜23:59）で指定してください")


def effective_order_date(
    now_jst: dt.datetime,
    deadline_time: dt.time | None,
    company_holidays: set[dt.date] | None = None,
) -> dt.date:
    """〆切時刻を考慮した実効受注日（スケジュール計算の起算日）を返す.

    - 現在時刻(JST) ≥ 〆切時刻 → 翌営業日（〆切超過。当日発注に間に合わない）
    - 現在時刻(JST) < 〆切時刻、または〆切未設定 → 当日（現行動作＝後方互換）

    〆切ちょうど（==）は「超過」とみなし翌営業日起算とする。

    Args:
        now_jst: 実際の受注時刻（JST・tz-aware）
        deadline_time: 注文〆切時刻。None は無効（当日起算）
        company_holidays: TOSYO独自休日の日付セット

    Returns:
        実効受注日（起算日）。add_business_days はこの日の翌日から営業日を数える。
    """
    today = now_jst.date()
    if deadline_time is not None and now_jst.time() >= deadline_time:
        return next_business_day(today, company_holidays)
    return today
