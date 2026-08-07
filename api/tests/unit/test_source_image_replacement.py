"""Unit tests for manufacturing source image replacement (元画像の差し替え)."""

import io
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from app.models.manufacturing_data import ManufacturingData, MfgDataStatus
from app.services import manufacturing_data_service as mds
from app.services.manufacturing_data_service import ManufacturingDataService
from app.utils.exceptions import ConflictError, NotFoundError, ValidationError

PNG = b"\x89PNG\r\n\x1a\n" + b"payload"


def _upload(filename: str = "new_color.png", content: bytes = PNG) -> UploadFile:
    """multipart アップロードの代用（Starlette の UploadFile をそのまま使う）."""
    return UploadFile(file=io.BytesIO(content), filename=filename)


def _md(
    *,
    status: str = MfgDataStatus.READY.value,
    source_images: list[Any] | None = None,
) -> ManufacturingData:
    md = ManufacturingData(product_code="RKSYO-1", product_type="acrylic_keychain")
    md.id = "md-1"
    md.status = status
    md.attempts = 1
    md.size = "50x50mm"
    md.variant = "clear"
    md.source_images = (
        source_images
        if source_images is not None
        else [
            {"layer_type": "color", "url": "https://x/color.png"},
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
        ]
    )
    md.created_at = datetime.now(UTC)
    md.updated_at = datetime.now(UTC)
    return md


def _service(md: ManufacturingData | None, *, storage=None, order_repo=None, **kwargs) -> Any:
    md_repo = AsyncMock()
    md_repo.find_by_id.return_value = md
    md_repo.find_by_cache_key.return_value = md
    if order_repo is None:
        order_repo = AsyncMock()
        order_repo.has_manufacturing_or_delivered_items.return_value = False
    svc = ManufacturingDataService(
        md_repo=md_repo,
        order_repo=order_repo,
        session=None,  # unit test: _commit は no-op
        file_storage=storage or _storage(),
        **kwargs,
    )
    return svc


def _storage(save_path: str = "source_images/20260726_abcd1234.png") -> Any:
    storage = MagicMock()
    storage.save = AsyncMock(return_value=save_path)
    storage.get = AsyncMock(return_value=PNG)
    return storage


class TestReplaceSourceImages:
    @pytest.mark.asyncio
    async def test_replaces_layer_and_restarts_generation(self) -> None:
        md = _md()
        storage = _storage()
        svc = _service(md, storage=storage)
        bg = MagicMock()

        resp = await svc.replace_source_images(
            "md-1",
            {"color": _upload()},
            replaced_by="admin@example.com",
            background_tasks=bg,
        )

        # 指定レイヤーだけが file_path 形式に置き換わり、他は元の URL を保つ
        assert md.source_images == [
            {
                "layer_type": "color",
                "file_path": "source_images/20260726_abcd1234.png",
                "filename": "new_color.png",
            },
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
        ]
        assert storage.save.await_args.kwargs["prefix"] == "source_images"
        # 差し替え履歴を記録
        assert md.source_images_replaced_at is not None
        assert md.source_images_replaced_by == "admin@example.com"
        # 再生成の波及（pending へ戻す・発注済み明細を降格・バックグラウンド起動）
        assert md.status == MfgDataStatus.PENDING.value
        svc._order_repo.sync_item_status_for_manufacturing_data.assert_awaited_once_with(
            "md-1", ready=False
        )
        bg.add_task.assert_called_once()
        # レスポンスは由来つきのレイヤー一覧を返す
        assert [(ly.layer_type, ly.origin) for ly in resp.source_images] == [
            ("color", "uploaded"),
            ("cutline", "external"),
        ]
        assert resp.source_images[0].filename == "new_color.png"
        assert resp.source_images[1].url == "https://x/cutline.png"

    @pytest.mark.asyncio
    async def test_replaces_multiple_layers_with_single_generation(self) -> None:
        md = _md()
        svc = _service(md)
        bg = MagicMock()

        await svc.replace_source_images(
            "md-1",
            {"color": _upload("c.png"), "cutline": _upload("k.png")},
            replaced_by="admin@example.com",
            background_tasks=bg,
        )

        assert [img["filename"] for img in md.source_images] == ["c.png", "k.png"]
        bg.add_task.assert_called_once()  # 再生成は1回だけ

    @pytest.mark.asyncio
    async def test_missing_row_raises_not_found(self) -> None:
        with pytest.raises(NotFoundError):
            await _service(None).replace_source_images(
                "missing",
                {"color": _upload()},
                replaced_by=None,
                background_tasks=MagicMock(),
            )

    @pytest.mark.asyncio
    async def test_rejects_while_generating(self) -> None:
        md = _md(status=MfgDataStatus.GENERATING.value)
        svc = _service(md)
        bg = MagicMock()

        with pytest.raises(ConflictError):
            await svc.replace_source_images(
                "md-1", {"color": _upload()}, replaced_by=None, background_tasks=bg
            )

        assert md.source_images_replaced_at is None
        bg.add_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_when_shared_with_manufacturing_order(self) -> None:
        md = _md()
        order_repo = AsyncMock()
        order_repo.has_manufacturing_or_delivered_items.return_value = True
        svc = _service(md, order_repo=order_repo)
        bg = MagicMock()

        with pytest.raises(ConflictError):
            await svc.replace_source_images(
                "md-1", {"color": _upload()}, replaced_by=None, background_tasks=bg
            )

        assert md.status == MfgDataStatus.READY.value  # 状態は変えない
        bg.add_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_row_without_source_images(self) -> None:
        # マッピング不能で作られた failed 行など、元データを持たない行は差し替え対象外。
        md = _md(status=MfgDataStatus.FAILED.value, source_images=[])
        with pytest.raises(ConflictError):
            await _service(md).replace_source_images(
                "md-1",
                {"color": _upload()},
                replaced_by=None,
                background_tasks=MagicMock(),
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "uploads",
        [
            pytest.param({}, id="no-layer-specified"),
            # 行に存在しないレイヤー（レイヤー構成の変更は不可）
            pytest.param({"white": _upload()}, id="layer-not-on-row"),
        ],
    )
    async def test_rejects_invalid_layer_specification(self, uploads: Any) -> None:
        md = _md()
        storage = _storage()
        svc = _service(md, storage=storage)

        with pytest.raises(ValidationError):
            await svc.replace_source_images(
                "md-1",
                uploads,
                replaced_by=None,
                background_tasks=MagicMock(),
            )

        storage.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_non_png_upload(self) -> None:
        md = _md()
        storage = _storage()
        svc = _service(md, storage=storage)

        with pytest.raises(ValidationError, match="PNG"):
            await svc.replace_source_images(
                "md-1",
                {"color": _upload("fake.png", b"GIF89a-not-a-png")},
                replaced_by=None,
                background_tasks=MagicMock(),
            )

        storage.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_upload_over_size_limit(self) -> None:
        md = _md()
        storage = _storage()
        svc = _service(md, storage=storage, max_source_bytes=4)

        with pytest.raises(ValidationError):
            await svc.replace_source_images(
                "md-1",
                {"color": _upload()},
                replaced_by=None,
                background_tasks=MagicMock(),
            )

        storage.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_failure_saves_nothing(self) -> None:
        # 2件目が不正なら1件目も保存しない（中途半端な差し替えを作らない）。
        md = _md()
        storage = _storage()
        svc = _service(md, storage=storage)

        with pytest.raises(ValidationError):
            await svc.replace_source_images(
                "md-1",
                {"color": _upload(), "cutline": _upload("bad.png", b"not-png")},
                replaced_by=None,
                background_tasks=MagicMock(),
            )

        storage.save.assert_not_called()
        assert md.source_images[0] == {"layer_type": "color", "url": "https://x/color.png"}


class TestSourceImageAccess:
    @pytest.mark.asyncio
    async def test_get_detail_reports_layer_origin(self) -> None:
        md = _md(
            source_images=[
                {"layer_type": "color", "file_path": "source_images/a.png", "filename": "a.png"},
                {"layer_type": "cutline", "url": "https://x/cutline.png"},
            ]
        )
        detail = await _service(md).get_detail("md-1")
        assert [(ly.layer_type, ly.origin) for ly in detail.source_images] == [
            ("color", "uploaded"),
            ("cutline", "external"),
        ]

    @pytest.mark.asyncio
    async def test_get_source_image_returns_uploaded_file(self) -> None:
        md = _md(
            source_images=[
                {"layer_type": "color", "file_path": "source_images/a.png", "filename": "a.png"}
            ]
        )
        storage = _storage()
        content = await _service(md, storage=storage).get_source_image("md-1", "color")
        assert content == PNG
        storage.get.assert_awaited_once_with("source_images/a.png")

    @pytest.mark.asyncio
    async def test_get_source_image_404_for_external_layer(self) -> None:
        # 外部受注由来（URL のみ）は pod-admin 側に実体がないため 404。
        md = _md()
        with pytest.raises(NotFoundError):
            await _service(md).get_source_image("md-1", "color")

    @pytest.mark.asyncio
    async def test_get_source_image_404_when_file_missing(self) -> None:
        md = _md(
            source_images=[{"layer_type": "color", "file_path": "source_images/gone.png"}]
        )
        storage = _storage()
        storage.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await _service(md, storage=storage).get_source_image("md-1", "color")


class TestGenerationUsesReplacedSource:
    @pytest.mark.asyncio
    async def test_download_reads_stored_file_instead_of_url(self) -> None:
        source_images = [
            {"layer_type": "color", "file_path": "source_images/a.png", "filename": "a.png"},
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
        ]
        storage = _storage()
        svc = _service(_md(), storage=storage, allowed_source_hosts=frozenset({"x"}))
        svc._fetch_with_limit = AsyncMock(return_value=b"CUTLINE")

        images = await svc._download_source_images(source_images, {"color", "cutline"})

        assert images == {"color": PNG, "cutline": b"CUTLINE"}
        # 差し替え済みレイヤーは HTTP 取得しない
        assert svc._fetch_with_limit.await_count == 1
        storage.get.assert_awaited_once_with("source_images/a.png")

    @pytest.mark.asyncio
    async def test_missing_stored_file_skips_layer_only(self) -> None:
        # 保存済みファイルが失われても、他レイヤーの取得は継続する（必須不足は呼び出し側が判定）。
        source_images = [
            {"layer_type": "color", "file_path": "source_images/gone.png"},
            {"layer_type": "cutline", "url": "https://x/cutline.png"},
        ]
        storage = _storage()
        storage.get = AsyncMock(return_value=None)
        svc = _service(_md(), storage=storage, allowed_source_hosts=frozenset({"x"}))
        svc._fetch_with_limit = AsyncMock(return_value=b"CUTLINE")

        images = await svc._download_source_images(source_images, {"color", "cutline"})

        assert images == {"cutline": b"CUTLINE"}

    @pytest.mark.asyncio
    async def test_generate_sends_replaced_layer_to_vm(self) -> None:
        md = _md(
            status=MfgDataStatus.PENDING.value,
            source_images=[
                {"layer_type": "color", "file_path": "source_images/a.png", "filename": "a.png"},
                {"layer_type": "cutline", "file_path": "source_images/b.png", "filename": "b.png"},
            ],
        )
        storage = _storage()
        storage.get = AsyncMock(side_effect=[b"COLOR", b"CUTLINE"])
        storage.save = AsyncMock(return_value="manufacturing_data/out.ai")

        vm_client = MagicMock()
        vm_client.submit = AsyncMock(return_value="job-1")
        vm_client.wait_until_complete = AsyncMock(
            return_value=SimpleNamespace(output_filename="out.ai")
        )
        vm_client.download = AsyncMock(return_value=b"AI-BYTES")

        svc = _service(md, storage=storage, vm_client=vm_client)
        await svc.generate("md-1")

        assert md.status == MfgDataStatus.READY.value
        assert vm_client.submit.await_args.kwargs["images"] == {
            "color": b"COLOR",
            "cutline": b"CUTLINE",
        }


class TestIntakeKeepsReplacedSource:
    """再受注で元データを更新するとき、差し替え済みレイヤーを維持することのテスト."""

    def _intake_item(self, color_url: str = "https://x/new-color.png") -> Any:
        return SimpleNamespace(
            id="item-1",
            product_code="RKSYO-1",
            product_type="acrylic_keychain",
            size="50x50mm",
            source_images=[
                {"layer_type": "color", "url": color_url},
                {"layer_type": "cutline", "url": "https://x/cutline.png"},
            ],
            manufacturing_data_id=None,
            manufacturing_data=None,
            status=None,
        )

    async def _reintake(self, existing: Any, item: Any) -> Any:
        order_repo = AsyncMock()
        order_repo.find_by_id.return_value = SimpleNamespace(
            order_source_id="src-1", items=[item]
        )
        svc = _service(existing, order_repo=order_repo)
        return await svc.prepare_for_order("order-1")

    @pytest.mark.asyncio
    async def test_replaced_layer_survives_and_others_are_refreshed(self) -> None:
        # 差し替え後に生成が失敗した行を新規受注が拾っても、差し替えた色版は残す。
        uploaded_color = {"layer_type": "color", "file_path": "source_images/a.png"}
        existing = _md(
            status=MfgDataStatus.FAILED.value,
            source_images=[uploaded_color, {"layer_type": "cutline", "url": "https://x/old.png"}],
        )
        item = self._intake_item()

        to_generate = await self._reintake(existing, item)

        assert to_generate == ["md-1"]
        assert existing.status == MfgDataStatus.PENDING.value
        assert existing.source_images == [
            uploaded_color,  # 差し替えは維持
            {"layer_type": "cutline", "url": "https://x/cutline.png"},  # 受注値で更新
        ]

    @pytest.mark.asyncio
    async def test_row_without_replacement_is_fully_refreshed_from_intake(self) -> None:
        existing = _md(status=MfgDataStatus.FAILED.value, source_images=[])
        item = self._intake_item()

        await self._reintake(existing, item)

        assert existing.source_images == item.source_images


@pytest.mark.asyncio
async def test_replace_then_generate_end_to_end_in_memory() -> None:
    """差し替え → 生成 が同じ FileStorage 上で噛み合うことを確認する."""
    md = _md()
    saved: dict[str, bytes] = {}

    async def fake_save(upload: Any, prefix: Any="") -> Any:
        path = f"{prefix}/{upload.filename}"
        saved[path] = upload.read()
        return path

    storage = MagicMock()
    storage.save = AsyncMock(side_effect=fake_save)
    storage.get = AsyncMock(side_effect=lambda path: saved.get(path))

    vm_client = MagicMock()
    vm_client.submit = AsyncMock(return_value="job-1")
    vm_client.wait_until_complete = AsyncMock(
        return_value=SimpleNamespace(output_filename="out.ai")
    )
    vm_client.download = AsyncMock(return_value=b"AI")

    svc = _service(
        md, storage=storage, vm_client=vm_client, allowed_source_hosts=frozenset({"x"})
    )
    svc._fetch_with_limit = AsyncMock(return_value=b"CUTLINE")

    with patch.object(mds, "run_generation", AsyncMock()):
        await svc.replace_source_images(
            "md-1",
            {"color": _upload()},
            replaced_by="a@b.c",
            background_tasks=MagicMock(),
        )
    await svc.generate("md-1")

    # save が返したキーで生成側が読み出せている（差し替え→生成の受け渡しが噛み合う）
    assert vm_client.submit.await_args.kwargs["images"]["color"] == PNG
