"""Unit tests for SSRF-guarded, size-limited source image download."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services import manufacturing_data_service as mds
from app.services.manufacturing_data_service import (
    ManufacturingDataService,
    SourceImageTooLargeError,
)


def _service(**kwargs) -> Any:
    return ManufacturingDataService(
        md_repo=AsyncMock(), order_repo=AsyncMock(), session=None, **kwargs
    )


class _StreamResp:
    def __init__(self, chunks: Any) -> None:
        self._chunks = chunks

    def raise_for_status(self) -> None:
        return None

    async def aiter_bytes(self) -> AsyncIterator[Any]:
        for c in self._chunks:
            yield c


class _StreamCtx:
    def __init__(self, resp: Any) -> None:
        self._resp = resp

    async def __aenter__(self) -> Any:
        return self._resp

    async def __aexit__(self, *exc) -> bool:
        return False


def _fake_client_factory(chunks_by_marker: Any) -> Any:
    """Return a fake httpx.AsyncClient class whose stream() picks chunks by url substring."""

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            # must tolerate timeout=..., follow_redirects=... kwargs
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *exc) -> bool:
            return False

        def stream(self, method: Any, url: Any) -> Any:
            for marker, chunks in chunks_by_marker.items():
                if marker in url:
                    return _StreamCtx(_StreamResp(chunks))
            raise httpx.ConnectError(f"unexpected url {url}")

    return _FakeClient


class TestDownloadSsrfGuard:
    @pytest.mark.asyncio
    async def test_skips_layer_that_fails_ssrf_guard(self) -> None:
        # color は許可ホスト経由、cutline は private IP リテラル宛 → ガードで弾かれ結果に含まれない
        source_images = [
            {"layer_type": "color", "url": "https://cdn.trusted/color.png"},
            {"layer_type": "cutline", "url": "https://10.0.0.5/cutline.png"},
        ]
        svc = _service(allowed_source_hosts=frozenset({"cdn.trusted"}))
        fake = _fake_client_factory({"color.png": [b"COLORBYTES"], "cutline.png": [b"NOPE"]})
        with patch.object(mds.httpx, "AsyncClient", fake):
            images = await svc._download_source_images(source_images, {"color", "cutline"})
        assert set(images.keys()) == {"color"}
        assert images["color"] == b"COLORBYTES"


class TestDownloadSizeLimit:
    @pytest.mark.asyncio
    async def test_skips_layer_exceeding_max_bytes(self) -> None:
        source_images = [
            {"layer_type": "color", "url": "https://cdn.trusted/color.png"},
            {"layer_type": "cutline", "url": "https://cdn.trusted/cutline.png"},
        ]
        # max 10 bytes: color streams 6 bytes (ok), cutline streams 8+8=16 bytes (too large)
        svc = _service(
            allowed_source_hosts=frozenset({"cdn.trusted"}), max_source_bytes=10
        )
        fake = _fake_client_factory(
            {"color.png": [b"123456"], "cutline.png": [b"AAAAAAAA", b"BBBBBBBB"]}
        )
        with patch.object(mds.httpx, "AsyncClient", fake):
            images = await svc._download_source_images(source_images, {"color", "cutline"})
        assert set(images.keys()) == {"color"}

    @pytest.mark.asyncio
    async def test_fetch_with_limit_raises_when_over_budget(self) -> None:
        svc = _service(max_source_bytes=4)
        fake = _fake_client_factory({"big": [b"ab", b"cd", b"ef"]})
        FakeClient = fake
        async with FakeClient() as client:
            with pytest.raises(SourceImageTooLargeError):
                await svc._fetch_with_limit(client, "https://cdn/big.png", 4)
