"""アプリケーションログの出力設定.

**uvicorn はルートロガーを設定しない。** 自前の `uvicorn.*` ロガーだけを構成し、
`disable_existing_loggers: False` で他をそのまま残す。結果として、アプリが出す
``logger.info(...)`` は**ハンドラのないルート**に伝播し、Python の最後の砦
（`logging.lastResort`、WARNING 以上・書式なし）でしか拾われない。

つまり、この設定を入れるまで本番では次の状態だった。

- ``logger.info`` は**どこにも出ない**（生成の成功・再試行の予定・復旧の件数が消える）
- ``logger.warning`` / ``logger.exception`` は出るが、**時刻もロガー名も重大度も付かない**
  素の stderr なので、Cloud Logging では一律 ERROR として並ぶ

障害のあとで何が起きたかを読むための材料が無いまま本番に出すことになるので、
**入口で 1 度だけ設定する。**

**設定は Settings ではなく環境変数から直接読む。** ログが最も要るのは Settings の
読み込みそのものが失敗したとき（必須の環境変数が無いなど）であり、そこに依存させると
その失敗だけが記録されないまま落ちる。

Cloud Run では構造化ログ（1 行 1 JSON）にする。`severity` と `message` は
Cloud Logging が解釈する予約キーであり、これがあるとログエクスプローラで
重大度の絞り込みとメッセージ検索がそのまま効く。ログベースのアラート
（`infra/modules/monitoring/`）もこの形に依存している。
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
from typing import Any

# Python の水準名 → Cloud Logging の severity。値が一致しないものだけ写す。
_SEVERITY = {
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
    "DEBUG": "DEBUG",
    "INFO": "INFO",
}

# 構造化ログに写さない LogRecord の属性（標準属性と、自前で別名にしたもの）。
_RESERVED = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


class CloudLoggingFormatter(logging.Formatter):
    """1 行 1 JSON で書き出す（Cloud Logging が構造化ログとして読む）."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": _SEVERITY.get(record.levelname, record.levelname),
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            # **例外は message に畳み込む。** 別キーに置くと、ログエクスプローラの
            # 既定表示（message だけ）でスタックトレースが見えなくなる。
            payload["message"] += "\n" + self.formatException(record.exc_info)
        # logger.info("...", extra={"md_id": ...}) で足した値をそのまま載せる。
        payload.update(
            {k: v for k, v in record.__dict__.items() if k not in _RESERVED}
        )
        return json.dumps(payload, ensure_ascii=False, default=str)


def _default_format() -> str:
    """実行環境から出力形式を決める（Cloud Run なら JSON、手元ならテキスト）.

    ``K_SERVICE`` は Cloud Run が必ず入れる環境変数である。**設定し忘れが起きない**
    ように、人が渡す値ではなく実行環境そのものから決める。
    """
    return "json" if os.getenv("K_SERVICE") else "text"


def configure_logging(level: str | None = None, log_format: str | None = None) -> None:
    """ルートロガーを構成する（プロセスの入口で 1 度だけ呼ぶ）.

    **冪等である。** dictConfig はルートのハンドラを置き換えるので、2 度呼んでも
    ハンドラは重複しない。
    """
    level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    log_format = (log_format or os.getenv("LOG_FORMAT") or _default_format()).lower()

    formatter: dict[str, Any] = (
        {"()": CloudLoggingFormatter}
        if log_format == "json"
        else {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}
    )

    logging.config.dictConfig(
        {
            "version": 1,
            # **既存のロガーを殺さない。** uvicorn と SQLAlchemy は import の時点で
            # 自分のロガーを作っており、無効化すると起動ログごと消える。
            "disable_existing_loggers": False,
            "formatters": {"app": formatter},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "app",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["stdout"], "level": level},
            "loggers": {
                # uvicorn は既定で自前のハンドラを持つ。**外して root に流す**ことで、
                # アプリのログと同じ書式・同じ重大度の付き方に揃える。
                # 揃えないと、同じ 1 リクエストの記録が 2 つの形式に分かれる。
                "uvicorn": {"handlers": [], "propagate": True},
                "uvicorn.error": {"handlers": [], "propagate": True},
                "uvicorn.access": {"handlers": [], "propagate": True},
            },
        }
    )
