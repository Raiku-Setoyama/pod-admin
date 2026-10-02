"""アプリのログを Cloud Logging で読める形で出す.

**設定しないと INFO が消える。** uvicorn が設定するのは自分のロガー（uvicorn.*）だけで、
`app.*` のロガーはハンドラの無いルートへ流れる。そのとき Python は最後の手段として
WARNING 以上だけを書式なしで stderr に出すので、INFO（メール送信の成否など）は
どこにも残らなかった（2026-10-02 に判明）。

Cloud Run では 1 行 1 個の JSON を stdout に書くと、Cloud Logging が ``severity`` を
重大度として、``message`` を本文として読む。素のテキストを stderr に書くと、
INFO まで ERROR 扱いになる。手元（Cloud Run 以外）では人が読みやすい素のテキストにする。
"""

from __future__ import annotations

import json
import logging
import os
import sys

# 素のテキストの書式。ワーカー（app/worker.py）も同じものを使う。
TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class CloudLoggingFormatter(logging.Formatter):
    """1 行 1 個の JSON（Cloud Logging の構造化ログ）にする."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            # 本文にスタックトレースを含めると Error Reporting が拾う
            message = f"{message}\n{self.formatException(record.exc_info)}"
        return json.dumps(
            {"severity": record.levelname, "message": message, "logger": record.name},
            ensure_ascii=False,
        )


# ルートに水準を与えると、これまで捨てられていた依存ライブラリの INFO が一斉に出る。
#
# **とくに httpx は 1 リクエスト 1 行である。** 製造データ 1 件の生成は VM の完了待ちを
# 5 秒間隔で最大 360 秒ポーリングするので、それだけで 70 行を超える。読む人は居ないうえに、
# Cloud Logging の取り込みは従量なので静かに費用になる。
_NOISY = ("httpx", "httpcore", "urllib3", "google", "asyncio")


def quiet_noisy_dependencies() -> None:
    """依存ライブラリのロガーを WARNING に落とす.

    **ルートにハンドラを付けるすべての経路から呼ぶ。** ワーカー（app/worker.py）は
    basicConfig を使っていて configure_logging を通らないので、あちらでも呼んでいる。
    """
    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)


def configure_logging(level: int = logging.INFO) -> None:
    """ルートロガーにハンドラを付ける（何度呼んでも 1 つだけ）."""
    # K_SERVICE は Cloud Run の**サービス**（API）にだけ入る。ワーカー（Job）には使わない:
    # ワーカーのログは素のテキストのまま、ログベース指標が textPayload で数えている
    # （infra/modules/manufacturing-monitoring）。JSON にすると指標が数えられなくなる。
    on_cloud_run = bool(os.getenv("K_SERVICE"))
    handler = logging.StreamHandler(sys.stdout if on_cloud_run else sys.stderr)
    handler.setFormatter(
        CloudLoggingFormatter() if on_cloud_run else logging.Formatter(TEXT_FORMAT)
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    quiet_noisy_dependencies()
