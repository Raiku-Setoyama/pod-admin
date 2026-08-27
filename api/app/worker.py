"""製造データ生成ワーカー（コンテナ実行基盤のジョブとして起動する）.

定期実行の仕組み（Cloud Scheduler）がこのジョブを起動する。生成待ちの製造データを
古い順に処理し、対象が無くなるか上限に達したら終了する。

なぜサービスではなくジョブなのか（ADR-0026）:
    Cloud Run の**サービス**はリクエストを処理している間しか CPU が割り当てられないため、
    30〜360 秒かかる生成をレスポンス送出後に走らせると完走しない。**ジョブ**は CPU が
    常時割り当てられ、実行時間の上限も十分に長いので、この制約を受けない。

多重起動:
    起動間隔より処理が長引けば実行は重なる。2 本目は Postgres のアドバイザリロックを
    取れずに即終了する。illustrator-vm が 1 件ずつの直列処理である以上、並列に走らせても
    速くならないうえ、復旧処理（generating の巻き戻し）が他方の処理中の行を壊す。

    行単位の二重処理は、ロックとは別に claim_for_generation の条件付き UPDATE が防いでいる。

モデルの読み込み:
    ``app.models`` を import する。モデルどうしは文字列で関連を張っているため、一部しか
    読み込まれていないとクエリの組み立てで名前を解決できずに落ちる。実際にはこの入口が
    間接的に読む ``app.models.*`` のどれか 1 つで全モデルが揃うが、**それが成り立つかどうかが
    他モジュールの import 順に左右されないよう**、ここで明示しておく。
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import text

import app.models  # noqa: F401  # 全モデルをマッパー登録に載せる（docstring 参照）
from app.config import settings
from app.database import get_engine
from app.services.manufacturing_data_service import (
    next_pending_generation_id,
    reclaim_stranded_generations,
    run_generation,
)

logger = logging.getLogger(__name__)

# このワーカー専用のアドバイザリロックのキー。他の用途と衝突しない固定値を持つ。
_ADVISORY_LOCK_KEY = 8_240_517_301

async def process_pending(*, max_runtime_seconds: float, max_items: int) -> int:
    """生成待ちの製造データを順に処理し、処理した件数を返す.

    打ち切っても取りこぼしにはならない。残りは pending のまま次回の起動が拾う。

    ``attempted`` を持つのは、処理しても pending から外れなかった行で無限ループに
    陥らないため（本来は generating→ready/failed へ進むので起こらないが、確定に
    失敗した場合に同じ行を延々と掴み続けるのを防ぐ）。
    """
    started = time.monotonic()
    processed = 0
    attempted: set[str] = set()

    while True:
        if max_items > 0 and processed >= max_items:
            logger.info(
                "reached the item limit (%d); leaving the rest for the next run", max_items
            )
            break

        elapsed = time.monotonic() - started
        if elapsed >= max_runtime_seconds:
            logger.info(
                "reached the runtime limit (%.0fs); leaving the rest for the next run",
                max_runtime_seconds,
            )
            break

        md_id = await next_pending_generation_id(attempted)
        if md_id is None:
            break

        attempted.add(md_id)
        await run_generation(md_id)
        processed += 1

    return processed


async def run_once() -> int:
    """ワーカーを 1 回走らせ、処理した件数を返す.

    アドバイザリロックを取れなければ、別のワーカーが動いているので何もせずに戻る。
    """
    engine = get_engine()
    async with engine.connect() as conn:
        acquired = bool(
            (
                await conn.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}
                )
            ).scalar()
        )
        if not acquired:
            logger.info("another worker is running; exiting without doing anything")
            return 0

        # ロックを取った時点でトランザクションを閉じる。アドバイザリロックは接続に
        # 紐づくのでコミットしても保持されるが、閉じないと最大 WORKER_MAX_RUNTIME_SECONDS
        # のあいだ idle in transaction の接続が居座り、VACUUM を止めてしまう。
        await conn.commit()

        try:
            reclaimed = await reclaim_stranded_generations()
            if reclaimed:
                logger.info("reclaimed %d stranded generation(s)", reclaimed)
            return await process_pending(
                max_runtime_seconds=settings.WORKER_MAX_RUNTIME_SECONDS,
                max_items=settings.WORKER_MAX_ITEMS,
            )
        finally:
            # **この解放は必須である。** SQLAlchemy の close は DBAPI 接続をプールへ
            # 返すだけで閉じないため、セッションに紐づくアドバイザリロックは
            # 解放されない。返さないと次回以降のワーカーが永久にロックを取れなくなる。
            await conn.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _ADVISORY_LOCK_KEY}
            )
            await conn.commit()


def main() -> None:
    """ジョブのエントリポイント（`python -m app.worker`）."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    processed = asyncio.run(run_once())
    logger.info("worker finished (processed=%d)", processed)


if __name__ == "__main__":
    main()
