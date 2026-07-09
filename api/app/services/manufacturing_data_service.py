"""Manufacturing data service.

外部注文（v2）の製造データを illustrator-vm で生成し、pod-admin 側に自前保存する。

- 商品×サイズ×バリアント単位でキャッシュ（同一商品の再注文で VM を再度呼ばない）。
- 生成は非同期（intake をブロックしない）。BackgroundTasks で新規セッションを開いて実行。
- VM の72h削除に依存せず、完了ジョブは速やかに DL して FileStorage に保存。
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session_maker
from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import OrderItem
from app.repositories.manufacturing_data_repository import ManufacturingDataRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.manufacturing_data import (
    ManufacturingDataListResponse,
    ManufacturingDataResponse,
)
from app.services.illustrator_vm_client import IllustratorVmClient, IllustratorVmError
from app.utils.exceptions import ConflictError, NotFoundError
from app.utils.file_storage import FileStorage, LocalFileStorage
from app.utils.mfg_product_mapping import MfgMappingError, build_vm_mapping

logger = logging.getLogger(__name__)

# 生成済みファイルの保存先プレフィックス（FileStorage 上）
_STORAGE_PREFIX = "manufacturing_data"

# 元データ（PNGレイヤー）ダウンロードのタイムアウト
_SOURCE_DOWNLOAD_TIMEOUT = 30.0

# recover_stranded_generations が起動した復旧タスクの強参照を保持する集合。
# create_task の戻り値を保持しないとタスクが GC で途中消滅しうるため。
_recovery_tasks: set[asyncio.Task[None]] = set()


class _BytesUpload:
    """FileStorage.save に生バイト列を渡すための最小アダプタ."""

    def __init__(self, content: bytes, filename: str) -> None:
        self._content = content
        self.filename = filename

    def read(self) -> bytes:
        return self._content

    def seek(self, offset: int) -> None:  # pragma: no cover - 呼ばれない
        pass


class ManufacturingDataService:
    """製造データの解決・生成・リトライを担うサービス."""

    def __init__(
        self,
        md_repo: ManufacturingDataRepository,
        order_repo: OrderRepository,
        session: AsyncSession | None = None,
        file_storage: FileStorage | None = None,
        vm_client: IllustratorVmClient | None = None,
    ) -> None:
        self._md_repo = md_repo
        self._order_repo = order_repo
        self._session = session
        self._file_storage = file_storage
        self._vm_client = vm_client

    async def _commit(self) -> None:
        """バックグラウンド/リクエストのどちらでも確実に永続化する."""
        if self._session is not None:
            await self._session.commit()

    # === 着信時の紐付け（リクエストスコープ） ===

    async def prepare_for_order(self, order_id: str) -> list[str]:
        """v2 注文の各明細に製造データ行を紐付け、生成が必要な md_id を返す.

        製造データ行は intake 内で同期的に作成/紐付けする（manufacturing_data_id を
        即時に確定させることで発注ゲートを確実に機能させる）。生成そのものは行わない。
        """
        order = await self._order_repo.find_by_id(order_id)
        if not order:
            return []

        to_generate: list[str] = []
        for item in order.items:
            # v1 明細（product_code / source_images なし）は対象外
            if not (item.product_code and item.source_images):
                continue
            md, needs_generation = await self._resolve_or_create(order.order_source_id, item)
            item.manufacturing_data_id = md.id
            if needs_generation and md.id not in to_generate:
                to_generate.append(md.id)

        # 注文・明細・製造データ行を確定（バックグラウンド生成が別セッションから参照できるように）
        await self._commit()
        return to_generate

    def enqueue_generation(self, background_tasks, md_ids: list[str]) -> None:
        """製造データ生成をバックグラウンドで起動する（新規セッションで実行）."""
        for md_id in md_ids:
            background_tasks.add_task(run_generation, md_id)

    async def _resolve_or_create(
        self, order_source_id: str | None, item: OrderItem
    ) -> tuple[ManufacturingData, bool]:
        """キャッシュを検索し、無ければ作成する。(row, 生成が必要か) を返す."""
        layer_types = {img["layer_type"] for img in item.source_images}
        try:
            mapping = build_vm_mapping(item.product_type, item.size, layer_types)
        except MfgMappingError as exc:
            # マッピング不能 → failed 行を作成（発注ゲートで保留、管理者が気づける）
            md, _ = await self._insert_row(
                order_source_id,
                item,
                variant=None,
                status=MfgDataStatus.FAILED,
                error_message=str(exc),
            )
            return md, False

        existing = await self._md_repo.find_by_cache_key(
            order_source_id, item.product_code, item.size, mapping.variant
        )
        if existing:
            # 失敗行は元データを更新して再生成対象にする。それ以外はそのまま再利用。
            if existing.status == MfgDataStatus.FAILED.value:
                existing.status = MfgDataStatus.PENDING.value
                existing.error_message = None
                existing.source_images = item.source_images
                await self._md_repo.update(existing)
                return existing, True
            return existing, False

        # 新規作成。ただし同時受注の競合で _insert_row が既存行を回収した場合は
        # created=False となる（その場合は作成した側が生成を起動するので二重起動しない）。
        md, created = await self._insert_row(
            order_source_id,
            item,
            variant=mapping.variant,
            status=MfgDataStatus.PENDING,
            source_images=item.source_images,
        )
        return md, created

    async def _insert_row(
        self,
        order_source_id: str | None,
        item: OrderItem,
        *,
        variant: str | None,
        status: MfgDataStatus,
        source_images: list | None = None,
        error_message: str | None = None,
    ) -> tuple[ManufacturingData, bool]:
        """製造データ行を作成する（キャッシュキー競合時は既存行を再取得）.

        Returns:
            (row, created): created=True なら新規作成、False なら競合で既存行を回収した。
            回収時に created=False を返すことで、呼び出し側が生成を二重起動しないようにする。
        """
        md = ManufacturingData(
            order_source_id=order_source_id,
            product_code=item.product_code,
            product_type=item.product_type,
            size=item.size,
            variant=variant,
            status=status.value,
            source_images=source_images,
            error_message=error_message,
        )
        if self._session is not None:
            # 同時受注でキャッシュキーが競合しても intake を 500 にしないよう
            # SAVEPOINT 内で作成し、競合時は既存行を再取得する。
            try:
                async with self._session.begin_nested():
                    self._session.add(md)
                    await self._session.flush()
                return md, True
            except IntegrityError:
                existing = await self._md_repo.find_by_cache_key(
                    order_source_id, item.product_code, item.size, variant
                )
                if existing is not None:
                    return existing, False
                raise
        return await self._md_repo.create(md), True

    # === 生成ドライバ（バックグラウンド） ===

    async def generate(self, md_id: str) -> None:
        """1件の製造データを生成し、状態を ready/failed に確定させる."""
        md = await self._md_repo.find_by_id(md_id)
        if md is None:
            logger.warning("manufacturing data %s not found; skip generation", md_id)
            return
        if md.status == MfgDataStatus.READY.value:
            return  # 既に完成（冪等）

        # 二重生成防止: pending/failed の行だけを generating へ原子的に claim する。
        # 既に generating（別ワーカーが処理中）/ready なら claim できず抜ける
        # （重複した VM ジョブ投入・生成ファイルの孤立を防ぐ）。
        claimed = await self._md_repo.claim_for_generation(md_id)
        if not claimed:
            await self._commit()
            logger.info(
                "manufacturing data %s is already generating or ready; skip duplicate",
                md_id,
            )
            return

        # claim 成功。行の状態を確定させる（attempts はここで加算）。
        md.status = MfgDataStatus.GENERATING.value
        md.attempts += 1
        md.error_message = None
        await self._md_repo.update(md)
        await self._commit()

        try:
            if self._vm_client is None:
                raise IllustratorVmError(
                    "illustrator-vm is not configured (ILLUSTRATOR_VM_BASE_URL)"
                )
            if not md.source_images:
                raise IllustratorVmError("source_images is empty")

            layer_types = {img["layer_type"] for img in md.source_images}
            mapping = build_vm_mapping(md.product_type, md.size, layer_types)

            images = await self._download_source_images(
                md.source_images, set(mapping.usable_layers)
            )
            # 必須レイヤーが揃っているか最終確認
            missing = [layer for layer in mapping.required_layers if layer not in images]
            if missing:
                raise IllustratorVmError(f"failed to fetch required layers: {missing}")

            job_id = await self._vm_client.submit(
                product_type=mapping.product_type,
                size=mapping.size,
                variant=mapping.variant,
                input_mode=mapping.input_mode,
                images=images,
            )
            md.vm_job_id = job_id
            await self._md_repo.update(md)
            await self._commit()

            status = await self._vm_client.wait_until_complete(job_id)
            content = await self._vm_client.download(job_id)

            filename = status.output_filename or f"{md.id}{mapping.output_ext}"
            file_path = await self._save_file(content, filename)

            md.status = MfgDataStatus.READY.value
            md.output_filename = filename
            md.file_path = file_path
            md.file_size = len(content)
            md.error_message = None
            await self._md_repo.update(md)
            await self._commit()
            logger.info("manufacturing data %s generated (%s)", md_id, filename)
        except Exception as exc:  # noqa: BLE001 - 失敗は必ず行に記録して終える
            md.status = MfgDataStatus.FAILED.value
            md.error_message = str(exc)[:1000]
            await self._md_repo.update(md)
            await self._commit()
            logger.exception("manufacturing data generation failed for %s", md_id)

    async def _download_source_images(
        self, source_images: list, wanted: set[str]
    ) -> dict[str, bytes]:
        """必要なレイヤーの PNG を並列ダウンロードする.

        個々のレイヤー DL 失敗では例外を送出せず、成功したレイヤーのみを返す。
        必須レイヤー不足の判定は呼び出し側の missing チェックに委ねる。これにより、
        optional レイヤー（white 等）の取得失敗で生成全体を落とすことを防ぐ
        （return_exceptions=True で in-flight タスクの取りこぼしも起きない）。
        """
        targets = [img for img in source_images if img["layer_type"] in wanted]
        semaphore = asyncio.Semaphore(4)

        async with httpx.AsyncClient(timeout=_SOURCE_DOWNLOAD_TIMEOUT) as client:

            async def fetch(img: dict) -> tuple[str, bytes]:
                async with semaphore:
                    response = await client.get(img["url"])
                    response.raise_for_status()
                    return img["layer_type"], response.content

            results = await asyncio.gather(
                *[fetch(img) for img in targets], return_exceptions=True
            )

        images: dict[str, bytes] = {}
        for img, result in zip(targets, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning(
                    "failed to download source layer %s (%s): %s",
                    img["layer_type"],
                    img["url"],
                    result,
                )
                continue
            layer_type, content = result
            images[layer_type] = content
        return images

    async def _save_file(self, content: bytes, filename: str) -> str:
        """生成物を FileStorage に保存し、保存先パスを返す."""
        storage = self._file_storage or LocalFileStorage(settings.UPLOAD_DIR)
        return await storage.save(_BytesUpload(content, filename), prefix=_STORAGE_PREFIX)

    # === 管理API（リクエストスコープ） ===

    async def retry(self, md_id: str, background_tasks) -> ManufacturingDataResponse:
        """失敗した製造データ生成を手動で再駆動する.

        retry は failed 行の再実行のみ許可する。製造データ行は
        （受注元 × 商品コード × サイズ × バリアント）単位で複数注文に共有されるため、
        ready/generating/pending の行を無条件に巻き戻すと、その行を参照する他の注文の
        is_manufacturing_ready まで劣化させてしまう（生成済みファイルの喪失や、発注可能
        だった明細の再ブロックにつながる）。宙吊りになった generating/pending 行は起動時の
        復旧処理（recover_stranded_generations）が再駆動する。
        """
        md = await self._md_repo.find_by_id(md_id)
        if md is None:
            raise NotFoundError("ManufacturingData", md_id)
        if md.status != MfgDataStatus.FAILED.value:
            raise ConflictError(
                f"manufacturing data {md_id} is not in a failed state "
                f"(current status: {md.status}); retry is only allowed for failed rows"
            )

        md.status = MfgDataStatus.PENDING.value
        md.error_message = None
        await self._md_repo.update(md)
        await self._commit()

        background_tasks.add_task(run_generation, md_id)
        return ManufacturingDataResponse.model_validate(md)

    async def list(
        self,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        order_source_id: str | None = None,
        product_code: str | None = None,
    ) -> ManufacturingDataListResponse:
        """製造データ一覧を取得する."""
        rows, total = await self._md_repo.list(
            page=page,
            limit=limit,
            status=status,
            order_source_id=order_source_id,
            product_code=product_code,
        )
        return ManufacturingDataListResponse(
            items=[ManufacturingDataResponse.model_validate(r) for r in rows],
            total=total,
            page=page,
            limit=limit,
        )


async def run_generation(md_id: str) -> None:
    """バックグラウンドで新規セッションを開き、1件の製造データを生成する.

    BackgroundTasks から呼ばれる。リクエストのセッションや ORM を持ち込まず、
    プレーンな md_id だけを受け取る（外部注文通知と同型）。
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        service = ManufacturingDataService(
            md_repo=ManufacturingDataRepository(session),
            order_repo=OrderRepository(session),
            session=session,
            file_storage=LocalFileStorage(settings.UPLOAD_DIR),
            vm_client=IllustratorVmClient.from_settings(settings),
        )
        try:
            await service.generate(md_id)
        except Exception:  # noqa: BLE001 - バックグラウンドは絶対に落とさない
            await session.rollback()
            logger.exception("run_generation crashed for %s", md_id)


async def recover_stranded_generations() -> None:
    """起動時に宙吊りの製造データ生成を再駆動する.

    生成は in-process の BackgroundTask で走るため、生成中（generating）に API が
    再起動/デプロイ/クラッシュすると、その行は generating のまま取り残され、参照する
    注文が発注ゲートで恒久的に保留される。新プロセスには in-flight タスクが無いので、
    起動時点の generating は全て中断済み。generating を pending に戻したうえで、
    pending/generating だった行を再駆動する（generate() 側の claim で二重起動は防止される）。
    失敗しても起動は継続させる（例外は握って記録するだけ）。
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        repo = ManufacturingDataRepository(session)
        stranded = await repo.find_stranded()
        # 中断された generating は claim 可能な pending に戻す。
        for md in stranded:
            if md.status == MfgDataStatus.GENERATING.value:
                md.status = MfgDataStatus.PENDING.value
        await session.commit()
        stranded_ids = [md.id for md in stranded]

    if not stranded_ids:
        return

    logger.info("recovering %d stranded manufacturing generation(s)", len(stranded_ids))
    for md_id in stranded_ids:
        task = asyncio.create_task(run_generation(md_id))
        _recovery_tasks.add(task)
        task.add_done_callback(_recovery_tasks.discard)
