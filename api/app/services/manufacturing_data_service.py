"""Manufacturing data service.

外部注文（v2）の製造データを illustrator-vm で生成し、pod-admin 側に自前保存する。

- 商品×サイズ×バリアント単位でキャッシュ（同一商品の再注文で VM を再度呼ばない）。
- 生成は intake をブロックしない。intake は行を pending で作るだけで、実際の生成は
  ワーカー（app/worker.py）が別プロセスで拾う。コンテナ実行基盤ではレスポンス送出後に
  CPU が絞られるため、リクエスト内で生成を走らせると完走しない（ADR-0026）。
- VM の72h削除に依存せず、完了ジョブは速やかに DL して FileStorage に保存。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session_maker
from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.models.order import OrderItem, item_status_for_manufacturing_ready
from app.repositories.manufacturing_data_repository import ManufacturingDataRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.manufacturing_data import (
    ManufacturingDataDetailResponse,
    ManufacturingDataListResponse,
    ManufacturingDataResponse,
)
from app.services.illustrator_vm_client import IllustratorVmClient, IllustratorVmError
from app.utils.exceptions import ConflictError, NotFoundError, ValidationError
from app.utils.file_storage import FileStorage, build_file_storage
from app.utils.mfg_product_mapping import MfgMappingError, build_vm_mapping
from app.utils.url_guard import validate_source_url

logger = logging.getLogger(__name__)


class SourceImageTooLargeError(Exception):
    """元データ画像がサイズ上限を超えた場合のエラー."""


# 生成済みファイルの保存先プレフィックス（FileStorage 上）
_STORAGE_PREFIX = "manufacturing_data"

# 差し替えた元データ（PNGレイヤー）の保存先プレフィックス（FileStorage 上）
_SOURCE_IMAGE_PREFIX = "source_images"

# 元データ（PNGレイヤー）ダウンロードのタイムアウト
_SOURCE_DOWNLOAD_TIMEOUT = 30.0

# 元データ1レイヤーの既定サイズ上限（settings 未指定時のフォールバック）
_DEFAULT_SOURCE_MAX_BYTES = 25 * 1024 * 1024  # 25MB

# PNG のシグネチャ。差し替えアップロードが本当に PNG かを中身で確認する
# （VM は PNG レイヤーしか受け付けないため、拡張子や Content-Type は信用しない）。
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _redact_url(url: str) -> str:
    """ログ用にクエリ文字列（署名付きトークン等）を落としたURLを返す."""
    return url.split("?", 1)[0]


def _merge_uploaded_layers(
    current: list[dict[str, str]] | None, intake: list[dict[str, str]] | None
) -> list[dict[str, str]]:
    """元データを受注値へ更新する。ただし差し替え済みレイヤーは維持する.

    差し替え済み（file_path つき）レイヤーは管理者が是正した内容なので、外部受注が
    渡す元の URL では上書きしない。それ以外のレイヤーは最新の受注値を採用する。
    """
    uploaded = {img["layer_type"]: img for img in current or [] if img.get("file_path")}
    refreshed = [uploaded.pop(img["layer_type"], img) for img in intake or []]
    # 受注値に無くなった差し替え済みレイヤーも失わない
    return refreshed + list(uploaded.values())


class _BytesUpload:
    """FileStorage.save に生バイト列を渡すための最小アダプタ."""

    def __init__(self, content: bytes, filename: str) -> None:
        self._content = content
        self.filename: str | None = filename

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
        allowed_source_hosts: frozenset[str] | None = None,
        max_source_bytes: int | None = None,
    ) -> None:
        self._md_repo = md_repo
        self._order_repo = order_repo
        self._session = session
        self._file_storage = file_storage
        self._vm_client = vm_client
        # 元データ取得の SSRF/サイズ防御。None なら settings から解決。
        self._allowed_source_hosts = allowed_source_hosts
        self._max_source_bytes = max_source_bytes

    async def _commit(self) -> None:
        """バックグラウンド/リクエストのどちらでも確実に永続化する."""
        if self._session is not None:
            await self._session.commit()

    # === 着信時の紐付け（リクエストスコープ） ===

    async def prepare_for_order(self, order_id: str) -> list[str]:
        """v2 注文の各明細に製造データ行を紐付け、生成が必要な md_id を返す.

        製造データ行は intake 内で同期的に作成/紐付けする（manufacturing_data_id を
        即時に確定させることで発注ゲートを確実に機能させる）。生成そのものは行わない。

        戻り値は「この受付で新たに生成が必要になった行」の報告である。**ワーカーは
        これを使わない**（生成待ちは DB から自分で導出する）。キャッシュ再利用が効いた
        ことの確認に使えるため残している。
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
            # 統合ステータス: 製造データが既に ready（キャッシュ再利用）なら「発注済み」、
            # それ以外（生成待ち/生成中/失敗）は「発注準備中」で保持する。
            item.status = item_status_for_manufacturing_ready(
                md.status == MfgDataStatus.READY.value
            )
            if needs_generation and md.id not in to_generate:
                to_generate.append(md.id)

        # 明細の統合ステータスに合わせて Order.status を再導出する
        # （v2 で未 ready の明細があれば注文全体も「発注準備中」になる）。
        # update_order_derived_status は shipped/cancelled をスキップする。
        await self._order_repo.update_order_derived_status(order_id)

        # 注文・明細・製造データ行を確定（バックグラウンド生成が別セッションから参照できるように）
        await self._commit()
        return to_generate

    async def _resolve_or_create(
        self, order_source_id: str | None, item: OrderItem
    ) -> tuple[ManufacturingData, bool]:
        """キャッシュを検索し、無ければ作成する。(row, 生成が必要か) を返す."""
        # 呼び出し元（_generate_for_order）で両方の存在を確認済み
        assert item.product_code is not None
        assert item.source_images is not None
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
                existing.source_images = _merge_uploaded_layers(
                    existing.source_images, item.source_images
                )
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
        source_images: list[Any] | None = None,
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
                # 呼び出し元（_resolve_or_create）で product_code の存在を確認済み
                assert item.product_code is not None
                existing = await self._md_repo.find_by_cache_key(
                    order_source_id, item.product_code, item.size, variant
                )
                if existing is not None:
                    return existing, False
                raise
        return await self._md_repo.create(md), True

    # === 生成ドライバ（バックグラウンド） ===

    async def generate(self, md_id: str, lease_token: datetime) -> None:
        """**確保済みの**製造データを1件生成し、状態を ready/failed に確定させる.

        呼び出し側（ワーカー）が claim_next_generation で行を generating へ確保し、
        リースを打ってから呼ぶ。**この関数は確保をしない。**二重生成の防止は取り出しの
        1 文が担っており、ここで再度 claim すると自分の確保と衝突する。

        ``lease_token`` は取り出しが返したリース期限＝所有権の証明である。結果の書き戻しは
        この値が一致する間だけ通す。一致しなければ、生成に手間取っている間にリースが失効し、
        別のワーカーがこの行を再確保したということなので、**自分の結果を捨てる。**
        """
        md = await self._md_repo.find_by_id(md_id)
        if md is None:
            logger.warning("manufacturing data %s not found; skip generation", md_id)
            return
        if md.status != MfgDataStatus.GENERATING.value:
            # 取り出しの直後にしか呼ばれないはずなので、ここに来るのは呼び出し側の誤りである。
            logger.warning(
                "manufacturing data %s is %s, not claimed for generation; skip",
                md_id,
                md.status,
            )
            return

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
                order_id=md.id,
            )
            md.vm_job_id = job_id
            await self._md_repo.update(md)
            await self._commit()

            status = await self._vm_client.wait_until_complete(job_id)
            content = await self._vm_client.download(job_id)

            filename = status.output_filename or f"{md.id}{mapping.output_ext}"
            file_path = await self._save_file(content, filename)

            applied = await self._finish(
                md,
                lease_token,
                status=MfgDataStatus.READY.value,
                output_filename=filename,
                file_path=file_path,
                file_size=len(content),
                error_message=None,
            )
            if not applied:
                return
            # 生成完了を参照明細へ波及: 「発注準備中」→「発注済み」（発注可能に）。
            await self._order_repo.sync_item_status_for_manufacturing_data(
                md_id, ready=True
            )
            await self._commit()
            logger.info("manufacturing data %s generated (%s)", md_id, filename)
        except Exception as exc:  # noqa: BLE001 - 失敗は必ず行に記録して終える
            logger.exception("manufacturing data generation failed for %s", md_id)
            await self._finish(
                md,
                lease_token,
                status=MfgDataStatus.FAILED.value,
                error_message=str(exc)[:1000],
            )
            await self._commit()

    async def _finish(
        self, md: ManufacturingData, lease_token: datetime, **values: Any
    ) -> bool:
        """リースを保持している間だけ結果を書き戻し、書けたかどうかを返す.

        書き戻しは条件付き UPDATE で行う。**先に ORM インスタンスを書き換えてはならない。**
        書き換えるとコミット時の flush が無条件にその値を書き、条件付き UPDATE の意味が
        消える。適用できたときだけ、手元のインスタンスにも同じ値を反映する
        （後続の flush は同じ値を書くだけになる）。
        """
        applied = await self._md_repo.finish_generation(
            md.id, lease_token=lease_token, values=values
        )
        if not applied:
            logger.warning(
                "lease for manufacturing data %s was lost while generating; "
                "discarding this result",
                md.id,
            )
            return False
        for field, value in values.items():
            setattr(md, field, value)
        md.lease_expires_at = None
        return True

    async def _download_source_images(
        self, source_images: list[Any], wanted: set[str]
    ) -> dict[str, bytes]:
        """必要なレイヤーの PNG を並列取得する.

        差し替え済みレイヤー（file_path つき）は FileStorage から読み、外部受注由来（url）は
        SSRF ガード付きで HTTP 取得する。

        個々のレイヤー取得失敗は fetch 内で握って None を返し、成功したレイヤーだけ集める。
        必須レイヤー不足の判定は呼び出し側の missing チェックに委ねる。これにより optional
        レイヤー（white 等）の取得失敗で生成全体を落とさない。
        """
        targets = [img for img in source_images if img["layer_type"] in wanted]
        semaphore = asyncio.Semaphore(4)
        allowed_hosts = (
            self._allowed_source_hosts
            if self._allowed_source_hosts is not None
            else frozenset(settings.SOURCE_IMAGE_ALLOWED_HOSTS)
        )
        max_bytes = self._max_bytes()

        # redirect 追従は無効（許可外ホストへの 30x リダイレクト経由の SSRF を防ぐ）。
        async with httpx.AsyncClient(
            timeout=_SOURCE_DOWNLOAD_TIMEOUT, follow_redirects=False
        ) as client:

            async def fetch(img: dict[str, Any]) -> tuple[str, bytes] | None:
                async with semaphore:
                    try:
                        if img.get("file_path"):
                            # 差し替え済み: 自前ストレージから読む（外部取得しない）。
                            content = await self._read_stored_source(img["file_path"])
                        else:
                            # SSRF ガード: 取得前に宛先URLを検証（内部・メタデータ等を遮断）。
                            validate_source_url(img["url"], allowed_hosts=allowed_hosts)
                            content = await self._fetch_with_limit(
                                client, img["url"], max_bytes
                            )
                        return img["layer_type"], content
                    except Exception as exc:  # noqa: BLE001 - 1レイヤーの失敗で全体を止めない（Unsafe/TooLarge含む）
                        logger.warning(
                            "failed to load source layer %s (%s): %s",
                            img["layer_type"],
                            _redact_url(img.get("file_path") or img.get("url", "")),
                            exc,
                        )
                        return None

            results = await asyncio.gather(*[fetch(img) for img in targets])

        return dict(r for r in results if r is not None)

    async def _fetch_with_limit(
        self, client: httpx.AsyncClient, url: str, max_bytes: int
    ) -> bytes:
        """URL をストリーミング取得し、max_bytes を超えたら中断して例外を投げる."""
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            total = 0
            chunks: list[bytes] = []
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise SourceImageTooLargeError(
                        f"source image exceeds {max_bytes} bytes: {_redact_url(url)}"
                    )
                chunks.append(chunk)
        return b"".join(chunks)

    def _storage(self) -> FileStorage:
        """FileStorage を解決する（未注入なら settings から構築）."""
        return self._file_storage or build_file_storage(settings)

    def _max_bytes(self) -> int:
        """元データ1レイヤーのサイズ上限を解決する（未注入なら settings から）."""
        return self._max_source_bytes or settings.SOURCE_IMAGE_MAX_BYTES

    async def _save_file(self, content: bytes, filename: str) -> str:
        """生成物を FileStorage に保存し、保存先パスを返す."""
        return await self._storage().save(
            _BytesUpload(content, filename), prefix=_STORAGE_PREFIX
        )

    async def _read_stored_source(self, file_path: str) -> bytes:
        """差し替え済み元データを FileStorage から読む."""
        content = await self._storage().get(file_path)
        if content is None:
            raise FileNotFoundError(f"stored source image not found: {file_path}")
        return content

    # === 管理API（リクエストスコープ） ===

    async def retry(self, md_id: str) -> ManufacturingDataResponse:
        """失敗した製造データ生成を手動で再駆動する.

        retry は failed 行の再実行のみ許可する。製造データ行は
        （受注元 × 商品コード × サイズ × バリアント）単位で複数注文に共有されるため、
        ready/generating/pending の行を無条件に巻き戻すと、その行を参照する他の注文の
        is_manufacturing_ready まで劣化させてしまう（生成済みファイルの喪失や、発注可能
        だった明細の再ブロックにつながる）。中断されて宙吊りになった generating 行は、
        リースの失効（reclaim_expired_generation_leases）が pending へ戻す。
        """
        md = await self._require_row(md_id)
        if md.status != MfgDataStatus.FAILED.value:
            raise ConflictError(
                f"manufacturing data {md_id} is not in a failed state "
                f"(current status: {md.status}); retry is only allowed for failed rows"
            )

        md.status = MfgDataStatus.PENDING.value
        md.error_message = None
        await self._md_repo.update(md)
        await self._commit()
        return ManufacturingDataResponse.model_validate(md)

    async def regenerate(self, md_id: str) -> ManufacturingDataResponse:
        """製造データを手動で再作成（同じ元データで再生成）する（管理者操作）.

        メーカーが製造着手前（参照する明細が全て 発注準備中 / 発注済み）のときのみ許可する
        （_assert_rebuildable 参照）。元データは差し替えず、同じ source_images で作り直す。
        """
        md = await self._require_row(md_id)
        await self._assert_rebuildable(md)
        await self._restart_generation(md)
        return ManufacturingDataResponse.model_validate(md)

    async def get_detail(self, md_id: str) -> ManufacturingDataDetailResponse:
        """製造データ詳細（元画像レイヤー一覧つき）を取得する."""
        md = await self._require_row(md_id)
        return ManufacturingDataDetailResponse.model_validate(md)

    async def replace_source_images(
        self,
        md_id: str,
        uploads: dict[str, UploadFile],
        *,
        replaced_by: str | None,
    ) -> ManufacturingDataDetailResponse:
        """元画像（PNGレイヤー）を差し替えて製造データを再生成する（管理者操作）.

        Args:
            uploads: レイヤー種別 -> アップロードされた PNG。

        差し替え可否は regenerate と同じゲート（生成中でない・製造着手済みの注文と共有して
        いない）で判定する。差し替えは行が既に持つレイヤー種別の置き換えのみ許可する:
        レイヤー構成が変わるとバリアント（= キャッシュキー）の導出結果まで変わるため。

        アップロードは FileStorage に保存し、source_images の該当レイヤーを file_path 形式へ
        置き換える。以降の生成は外部 URL ではなく保存したファイルを読む。
        """
        md = await self._require_row(md_id)
        await self._assert_rebuildable(md)

        stored = md.source_images or []
        if not stored:
            raise ConflictError(
                f"manufacturing data {md_id} has no source images to replace"
            )
        self._validate_replacement_layers(uploads, stored)

        # 全ファイルを検証してから保存する（一部だけ差し替わった中途半端な状態を作らない）。
        validated = [
            (layer_type, file.filename or f"{layer_type}.png",
             await self._read_png_upload(layer_type, file))
            for layer_type, file in uploads.items()
        ]
        # 保存は並列（GCS の往復を直列に積み上げない）。
        paths = await asyncio.gather(
            *(
                self._storage().save(
                    _BytesUpload(content, filename), prefix=_SOURCE_IMAGE_PREFIX
                )
                for _, filename, content in validated
            )
        )
        replacements = {
            layer_type: {
                "layer_type": layer_type,
                "file_path": path,
                "filename": filename,
            }
            for (layer_type, filename, _), path in zip(validated, paths, strict=True)
        }

        # JSONB は再代入しないと変更が検知されないため、新しいリストを作って差し替える。
        md.source_images = [replacements.get(img["layer_type"], img) for img in stored]
        md.source_images_replaced_at = datetime.now(UTC)
        md.source_images_replaced_by = replaced_by

        await self._restart_generation(md)
        logger.info(
            "source images replaced for manufacturing data %s (layers=%s, by=%s)",
            md_id,
            sorted(replacements),
            replaced_by,
        )
        return ManufacturingDataDetailResponse.model_validate(md)

    async def get_source_image(self, md_id: str, layer_type: str) -> bytes:
        """差し替え済み元画像の内容を返す（プレビュー用）.

        外部受注由来（URL のみ）のレイヤーは pod-admin 側に実体を持たないため 404 とする
        （フロントは URL へのリンクを表示する）。
        """
        md = await self._require_row(md_id)
        stored = next(
            (
                img
                for img in md.source_images or []
                if img["layer_type"] == layer_type and img.get("file_path")
            ),
            None,
        )
        content = await self._storage().get(stored["file_path"]) if stored else None
        if content is None:
            raise NotFoundError("SourceImage", f"{md_id}/{layer_type}")
        return content

    async def _require_row(self, md_id: str) -> ManufacturingData:
        """製造データ行を取得する（無ければ 404）."""
        md = await self._md_repo.find_by_id(md_id)
        if md is None:
            raise NotFoundError("ManufacturingData", md_id)
        return md

    async def _assert_rebuildable(self, md: ManufacturingData) -> None:
        """製造データを作り直せる状態か検証する（regenerate / 元画像差し替えで共通）.

        生成中は進行中の VM ジョブと競合させないため拒否する。製造データ行は複数注文で
        共有されるため、1件でも「製造中」/「納入済み」の注文が参照している場合は、その注文の
        完成データを壊さないよう拒否する。
        """
        if md.status == MfgDataStatus.GENERATING.value:
            raise ConflictError(
                f"manufacturing data {md.id} is currently generating; "
                "regeneration is not allowed while a job is in progress"
            )
        if await self._order_repo.has_manufacturing_or_delivered_items(md.id):
            raise ConflictError(
                f"manufacturing data {md.id} is shared with an order already in "
                "manufacturing/delivered; regeneration is blocked to protect it"
            )

    async def _restart_generation(self, md: ManufacturingData) -> None:
        """行を pending に戻し、参照明細を降格させる（生成はワーカーが拾う）.

        呼び出し側が md に加えた変更（元画像の差し替え等）もここでまとめて永続化する。

        参照する「発注済み」明細は「発注準備中」へ戻す（demote）ことで、未完成の製造データで
        メーカー発注されるのを防ぐ。生成完了時に generate() が再び「発注済み」へ昇格させる。
        """
        md.status = MfgDataStatus.PENDING.value
        md.error_message = None
        await self._md_repo.update(md)
        await self._order_repo.sync_item_status_for_manufacturing_data(md.id, ready=False)
        await self._commit()

    @staticmethod
    def _validate_replacement_layers(
        uploads: dict[str, UploadFile], stored: list[dict[str, str]]
    ) -> None:
        """差し替え対象のレイヤーがこの行に存在するかを検証する.

        レイヤー種別の語彙・重複はエンドポイントのシグネチャ（レイヤーごとの名前付き
        ファイル項目）が保証するため、ここでは行との突き合わせだけを行う。
        """
        if not uploads:
            raise ValidationError("差し替える元画像を1件以上指定してください")

        stored_layers = {img["layer_type"] for img in stored}
        # レイヤーの追加・削除はキャッシュキー（導出バリアント）を変えるため許可しない。
        unknown = sorted(set(uploads) - stored_layers)
        if unknown:
            raise ValidationError(
                f"この製造データに存在しないレイヤー種別です: {unknown} "
                f"(現在のレイヤー: {sorted(stored_layers)})"
            )

    async def _read_png_upload(self, layer_type: str, file: UploadFile) -> bytes:
        """アップロードを読み、サイズ上限と PNG 形式（マジックバイト）を検証する."""
        max_bytes = self._max_bytes()
        too_large = (
            f"元画像のサイズが上限（{max_bytes} bytes）を超えています: {layer_type}"
        )
        # multipart を読み終えた時点で size は確定しているため、本文を読む前に弾ける。
        if file.size is not None and file.size > max_bytes:
            raise ValidationError(too_large)

        content = await file.read()
        if len(content) > max_bytes:
            raise ValidationError(too_large)
        if not content.startswith(_PNG_SIGNATURE):
            raise ValidationError(f"元画像は PNG 形式のみ対応しています: {layer_type}")
        return content

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


async def run_generation(md_id: str, lease_token: datetime) -> None:
    """新規セッションを開き、1件の製造データを生成する.

    ワーカー（app/worker.py）から呼ばれる。呼び出し元のセッションや ORM を持ち込まず、
    プレーンな md_id だけを受け取る。生成は 30〜360 秒かかりうるため、この関数を
    リクエストの処理中やレスポンス送出後に呼んではならない（ADR-0026）。
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        service = ManufacturingDataService(
            md_repo=ManufacturingDataRepository(session),
            order_repo=OrderRepository(session),
            session=session,
            file_storage=build_file_storage(settings),
            vm_client=IllustratorVmClient.from_settings(settings),
        )
        try:
            await service.generate(md_id, lease_token)
        except Exception:  # noqa: BLE001 - バックグラウンドは絶対に落とさない
            await session.rollback()
            logger.exception("run_generation crashed for %s", md_id)


async def claim_next_generation(lease_seconds: float) -> tuple[str, datetime] | None:
    """次に生成すべき製造データを1件確保し、``(id, リース期限)`` を返す。無ければ None.

    ワーカーから呼ばれる。run_generation と同じく、呼び出し元のセッションを持ち込まず
    新規セッションを開く。確保の意味は ManufacturingDataRepository.claim_next_generation を参照。
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        claimed = await ManufacturingDataRepository(session).claim_next_generation(
            lease_seconds
        )
        await session.commit()
        return claimed


async def reclaim_expired_generation_leases() -> int:
    """リースが切れた生成を pending へ戻し、戻した件数を返す.

    生成は別プロセスのワーカーが担うため、ワーカーが生成中（generating）に落ちると、
    その行は generating のまま取り残され、参照する注文が発注ゲートで恒久的に保留される。

    **この関数は単独で正しい。**期限内のリースを持つ行は誰かが処理中なので触らない。
    したがって、いつ・誰が・何本同時に呼んでも安全である。
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        reclaimed = await ManufacturingDataRepository(session).reclaim_expired_leases()
        await session.commit()
    return reclaimed
