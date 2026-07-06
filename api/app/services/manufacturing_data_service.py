"""Manufacturing data generation service.

外部注文(v2)の各明細について製造データをキャッシュ解決し、必要なら illustrator-vm で
生成して自前ストレージ(FileStorage)へ保存する。バックグラウンドワーカーから利用される。
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker
from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import OrderItem
from app.repositories.manufacturing_data_repository import ManufacturingDataRepository
from app.repositories.order_repository import OrderRepository
from app.services.illustrator_vm_client import IllustratorVmClient
from app.utils.exceptions import ValidationError
from app.utils.file_storage import BytesUpload, FileStorage, build_file_storage
from app.utils.mfg_product_mapping import resolve_vm_mapping, select_layers

logger = logging.getLogger(__name__)

_LAYER_DOWNLOAD_TIMEOUT = 60.0
_MFG_STORAGE_PREFIX = "manufacturing"


def is_generatable_item(item: OrderItem) -> bool:
    """製造データ生成対象の v2 明細か（product_code とレイヤーURLを持つ）."""
    return bool(item.product_code) and bool(item.source_images)


class ManufacturingDataService:
    """製造データのキャッシュ解決・生成ドライバ（バックグラウンドワーカーから利用）."""

    def __init__(
        self,
        session: AsyncSession,
        mfg_repo: ManufacturingDataRepository,
        order_repo: OrderRepository,
        file_storage: FileStorage,
        vm_client: IllustratorVmClient | None = None,
    ) -> None:
        self._session = session
        self._mfg_repo = mfg_repo
        self._order_repo = order_repo
        self._file_storage = file_storage
        self._vm_client = vm_client

    async def ensure_for_order(self, order_id: str) -> None:
        """注文の各 v2 明細について、製造データを解決（キャッシュ）＋必要なら生成する."""
        order = await self._order_repo.find_by_id(order_id)
        if order is None:
            logger.warning("ensure_for_order: order not found: %s", order_id)
            return
        if order.order_source_id is None:
            logger.warning("ensure_for_order: order %s has no order_source", order_id)
            return

        for item in order.items:
            if not is_generatable_item(item):
                continue
            md = await self._resolve_or_create(order.order_source_id, item)
            if md is None:
                continue
            item.manufacturing_data_id = md.id
            await self._session.commit()
            await self._maybe_generate(md)

    async def generate_by_id(self, mfg_data_id: str) -> None:
        """既存の manufacturing_data 行を（必要なら）生成する（手動リトライのワーカー用）."""
        md = await self._mfg_repo.get_by_id(mfg_data_id)
        if md is None:
            logger.warning("generate_by_id: not found: %s", mfg_data_id)
            return
        await self._maybe_generate(md)

    async def _resolve_or_create(
        self, order_source_id: str, item: OrderItem
    ) -> ManufacturingData | None:
        product_code = item.product_code
        size = item.size
        if not product_code or not size:
            return None
        try:
            mapping = resolve_vm_mapping(item.product_type, size, item.variant)
        except ValidationError:
            logger.exception(
                "resolve_or_create: unsupported combo product_type=%s size=%s variant=%s",
                item.product_type,
                size,
                item.variant,
            )
            return None

        variant = mapping.variant
        existing = await self._mfg_repo.find_by_cache_key(
            order_source_id, product_code, size, variant
        )
        if existing is not None:
            return existing

        md = ManufacturingData(
            order_source_id=order_source_id,
            product_code=product_code,
            product_type=item.product_type,
            size=size,
            variant=variant,
            status=MfgDataStatus.PENDING.value,
            source_images=item.source_images,
        )
        try:
            return await self._mfg_repo.create(md)
        except IntegrityError:
            # 別注文が同時に同一キーを作成 → ロールバックして再取得（重複生成防止）
            await self._session.rollback()
            return await self._mfg_repo.find_by_cache_key(
                order_source_id, product_code, size, variant
            )

    async def _maybe_generate(self, md: ManufacturingData) -> None:
        # ready かつ保存ファイルが存在 → キャッシュ再利用（VM を呼ばない）
        if (
            md.status == MfgDataStatus.READY.value
            and md.file_path
            and await self._file_storage.exists(md.file_path)
        ):
            return
        # ready だがファイル消失（GCS 180日ライフサイクル等）→ 再生成を許可
        allow_ready_stale = md.status == MfgDataStatus.READY.value
        await self._generate(md, allow_ready_stale=allow_ready_stale)

    async def _generate(self, md: ManufacturingData, *, allow_ready_stale: bool = False) -> None:
        if self._vm_client is None:
            logger.info("ILLUSTRATOR_VM_URL 未設定のため製造データ生成をスキップ: %s", md.id)
            return

        # 原子的に claim（多重生成防止）。claim 失敗＝他ワーカーが処理中 or 既に ready。
        claimed = await self._mfg_repo.claim_for_generation(md.id, allow_ready=allow_ready_stale)
        await self._session.commit()
        if not claimed:
            return
        await self._session.refresh(md)

        try:
            mapping = resolve_vm_mapping(md.product_type, md.size, md.variant)
            layers = select_layers(md.product_type, md.source_images)
            layer_bytes = await self._download_layers(layers)

            job_id = await self._vm_client.submit(
                product_type=md.product_type,
                vm_size=mapping.vm_size,
                variant=md.variant,
                input_mode=mapping.input_mode,
                order_id=md.product_code,  # VM の order_id は出力ファイル名にしか影響しない
                layers=layer_bytes,
            )
            md.vm_job_id = job_id
            await self._session.commit()

            final_status = await self._vm_client.wait_for_completion(job_id)
            content = await self._vm_client.download(job_id)
            filename = final_status.output_filename or f"{md.product_code}.{mapping.output_format}"
            path = await self._file_storage.save(
                BytesUpload(content, filename), prefix=_MFG_STORAGE_PREFIX
            )

            md.output_filename = filename
            md.file_path = path
            md.file_size = len(content)
            md.status = MfgDataStatus.READY.value
            md.error_message = None
            await self._session.commit()
            logger.info("製造データ生成完了: %s -> %s", md.id, path)
        except Exception as exc:
            await self._mark_failed(md.id, exc)

    async def _mark_failed(self, mfg_data_id: str, exc: Exception) -> None:
        await self._session.rollback()
        md = await self._mfg_repo.get_by_id(mfg_data_id)
        if md is not None:
            md.status = MfgDataStatus.FAILED.value
            md.error_message = str(exc)[:1000]
            await self._session.commit()
        logger.exception("製造データ生成に失敗: %s", mfg_data_id)

    async def _download_layers(self, layers: dict[str, str]) -> dict[str, bytes]:
        async with httpx.AsyncClient(timeout=_LAYER_DOWNLOAD_TIMEOUT) as client:

            async def fetch(layer_type: str, url: str) -> tuple[str, bytes]:
                response = await client.get(url)
                response.raise_for_status()
                return layer_type, response.content

            results: list[tuple[str, bytes]] = await asyncio.gather(
                *[fetch(lt, url) for lt, url in layers.items()]
            )
        return dict(results)


def _build_service(session: AsyncSession) -> ManufacturingDataService:
    return ManufacturingDataService(
        session=session,
        mfg_repo=ManufacturingDataRepository(session),
        order_repo=OrderRepository(session),
        file_storage=build_file_storage(),
        vm_client=IllustratorVmClient.from_settings(),
    )


async def run_ensure_for_order(order_id: str) -> None:
    """BackgroundTasks 用: 独自セッションで ensure_for_order を実行する."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            service = _build_service(session)
            await service.ensure_for_order(order_id)
        except Exception:
            logger.exception("run_ensure_for_order failed: %s", order_id)
            await session.rollback()


async def run_generate_manufacturing_data(mfg_data_id: str) -> None:
    """BackgroundTasks 用: 独自セッションで単一行の生成を実行する（手動リトライ）."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            service = _build_service(session)
            await service.generate_by_id(mfg_data_id)
        except Exception:
            logger.exception("run_generate_manufacturing_data failed: %s", mfg_data_id)
            await session.rollback()
