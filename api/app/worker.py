"""製造データ生成ワーカー（コンテナ実行基盤のジョブとして起動する）.

定期実行の仕組み（Cloud Scheduler）がこのジョブを起動する。生成待ちの製造データを
古い順に処理し、対象が無くなるか上限に達したら終了する。

なぜサービスではなくジョブなのか（ADR-0026）:
    Cloud Run の**サービス**はリクエストを処理している間しか CPU が割り当てられないため、
    30〜360 秒かかる生成をレスポンス送出後に走らせると完走しない。**ジョブ**は CPU が
    常時割り当てられ、実行時間の上限も十分に長いので、この制約を受けない。

多重起動:
    起動間隔より処理が長引けば実行は重なる。2 本目は Postgres のアドバイザリロックを
    取れずに即終了する。**これはスループットの都合であって、正しさの条件ではない。**
    illustrator-vm が 1 件ずつの直列処理である以上、ワーカーを並列に走らせても速くならず、
    VM のキュー上限（50 超で 503）を無駄に消費するだけだからである。

    **ロックを外しても壊れない。**同じ行を 2 度処理しないことは、キューからの取り出し
    （``claim_next_generation`` の 1 文）とリースが保証している。VM が並列化されたら、
    ロックを外すだけで並列ワーカーに移行できる。

VM の死活確認（2026-09-27〜10-02 の障害を受けて追加）:
    起動のたびに、取り出しより先に illustrator-vm の /health を 1 回叩き、結果を
    ``illustrator_vm_health status=ok|ng`` の形でログに残す。**生成待ちが無くても叩く。**
    注文が来ないと VM に触れず、止まっていても誰も気づけなかったためである。
    Cloud Logging のログベース指標とアラート（infra/modules/manufacturing-monitoring）がこの行を数える。

    NG のときは取り出さない。生成待ちは pending のまま VM の復旧を待ち、次の起動で
    自動的に拾われる（取り出して失敗させると、人が 1 件ずつ再生成を押すまで止まる）。

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
from datetime import UTC, datetime

from sqlalchemy import text

import app.models  # noqa: F401  # 全モデルをマッパー登録に載せる（docstring 参照）
from app.config import settings
from app.database import get_engine
from app.services.illustrator_vm_client import IllustratorVmClient
from app.services.manufacturing_data_service import (
    GenerationOutcome,
    claim_next_generation,
    pending_generation_summary,
    reclaim_expired_generation_leases,
    run_generation,
)

logger = logging.getLogger(__name__)

# このワーカー専用のアドバイザリロックのキー。他の用途と衝突しない固定値を持つ。
_ADVISORY_LOCK_KEY = 8_240_517_301

# ログの目印。Cloud Logging のログベース指標（infra/modules/manufacturing-monitoring）が
# この文字列で数えるので、**変えるときは指標のフィルタも同時に変える。**
LOG_MARK_VM_HEALTH = "illustrator_vm_health"
LOG_MARK_STALLED = "manufacturing_data_stalled"


async def process_pending(*, max_runtime_seconds: float, max_items: int) -> int:
    """生成待ちの製造データを順に処理し、処理した件数を返す.

    打ち切っても取りこぼしにはならない。残りは pending のまま次回の起動が拾う。

    取り出した時点で行は generating になりリースが打たれるので、次の周回で同じ行が
    返ってくることはない。処理の途中で落ちても、リースが切れれば pending へ戻る。
    """
    started = time.monotonic()
    processed = 0

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

        claimed = await claim_next_generation(settings.WORKER_LEASE_SECONDS)
        if claimed is None:
            break

        md_id, lease_token = claimed
        outcome = await run_generation(md_id, lease_token)
        if outcome is GenerationOutcome.DEFERRED:
            # 死活確認は通ったのに届かなかった。VM が不調になったので、残りは次回の
            # 起動に回す（次回はまず死活確認で止まる）。生成待ちへ戻しただけなので
            # 処理件数に数えない（数えると滞留の警告が出なくなる）。
            logger.warning("illustrator-vm became unreachable; leaving the rest for the next run")
            break
        processed += 1

    return processed


async def check_vm_health() -> bool:
    """illustrator-vm の死活を確かめ、結果を目印つきでログに残す.

    VM が設定されていない環境（ステージング等）では確認せず True を返す
    （取り出した行は generate() が「未設定」で failed にする。従来どおり）。
    """
    client = IllustratorVmClient.from_settings(settings)
    if client is None:
        logger.info("%s status=disabled", LOG_MARK_VM_HEALTH)
        return True
    health = await client.health()
    if health.ok:
        logger.info("%s status=ok", LOG_MARK_VM_HEALTH)
    else:
        logger.warning("%s status=ng detail=%s", LOG_MARK_VM_HEALTH, health.detail)
    return health.ok


async def report_pending(*, processed: int) -> None:
    """生成待ちの滞留をログに残す（長く動いていなければ目印つきで警告する）.

    この起動で 1 件でも処理していれば何もしない。大量の受注を順に捌いている最中は、
    後ろの行が 60 分待つことがあるが、それは止まっているのではない。
    """
    if processed > 0:
        return
    count, oldest = await pending_generation_summary()
    if oldest is None:  # 生成待ちが 0 件
        return
    idle_minutes = (datetime.now(UTC) - oldest).total_seconds() / 60
    if idle_minutes >= settings.WORKER_STALL_ALERT_MINUTES:
        logger.warning(
            "%s pending=%d oldest_idle_minutes=%.0f", LOG_MARK_STALLED, count, idle_minutes
        )
    else:
        logger.info("pending manufacturing data: %d (oldest idle %.0f min)", count, idle_minutes)


async def run_once() -> int:
    """ワーカーを 1 回走らせ、処理した件数を返す.

    アドバイザリロックを取れなければ、別のワーカーが動いているので何もせずに戻る
    （正しさの条件ではない。モジュールの docstring を参照）。
    """
    # 取り出しの可否に関わらず毎回確かめる（ロックを取れずに降りる起動でも）。
    # ログが途絶えたこと自体を「ワーカーが動いていない」として検知するためである。
    vm_healthy = await check_vm_health()

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
            # 正しさのためではなく、直列な VM を複数のワーカーで奪い合わないための降り方。
            logger.info("another worker is running; exiting without doing anything")
            return 0

        # ロックを取った時点でトランザクションを閉じる。アドバイザリロックは接続に
        # 紐づくのでコミットしても保持されるが、閉じないと最大 WORKER_MAX_RUNTIME_SECONDS
        # のあいだ idle in transaction の接続が居座り、VACUUM を止めてしまう。
        await conn.commit()

        try:
            reclaimed = await reclaim_expired_generation_leases()
            if reclaimed:
                logger.info("reclaimed %d generation(s) with an expired lease", reclaimed)
            processed = 0
            if vm_healthy:
                processed = await process_pending(
                    max_runtime_seconds=settings.WORKER_MAX_RUNTIME_SECONDS,
                    max_items=settings.WORKER_MAX_ITEMS,
                )
            else:
                logger.warning("illustrator-vm is unhealthy; leaving pending rows untouched")
            await report_pending(processed=processed)
            return processed
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
    warning = settings.lease_margin_warning()
    if warning:
        logger.warning("%s", warning)
    processed = asyncio.run(run_once())
    logger.info("worker finished (processed=%d)", processed)


if __name__ == "__main__":
    main()
