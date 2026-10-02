"""Unit tests for the illustrator-vm client (httpx MockTransport)."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.illustrator_vm_client import (
    IllustratorVmClient,
    IllustratorVmError,
    IllustratorVmUnavailableError,
)


@pytest.fixture(autouse=True)
def _no_sleep() -> Iterator[Any]:
    """リトライ/ポーリングの sleep を無効化してテストを高速化."""
    with patch("app.services.illustrator_vm_client.asyncio.sleep", new=AsyncMock()):
        yield


def _client(handler: Any, **kwargs: Any) -> IllustratorVmClient:
    return IllustratorVmClient(
        "http://vm.test",
        poll_interval=0,
        max_poll_seconds=5,
        max_retries=3,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


class TestSubmit:
    @pytest.mark.asyncio
    async def test_submit_returns_job_id_and_base64_encodes(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            import json

            captured["body"] = json.loads(request.content)
            return httpx.Response(202, json={"job_id": "job-1"})

        client = _client(handler)
        job_id = await client.submit(
            product_type="sticker",
            size="50x50",
            variant="clear",
            input_mode="multi",
            images={"color": b"\x89PNG-color", "cutline": b"\x89PNG-cut"},
            order_id="md-1",
        )
        assert job_id == "job-1"
        assert captured["path"] == "/api/process"
        body = captured["body"]
        # 実VM ProcessRequest: images は ImageInput の「配列」（dict ではない）
        assert isinstance(body["images"], list)
        by_type = {img["type"]: img for img in body["images"]}
        assert set(by_type) == {"color", "cutline"}
        # 各要素は type / data(base64) / filename を持つ
        import base64

        assert by_type["color"]["data"] == base64.b64encode(b"\x89PNG-color").decode()
        assert by_type["color"]["filename"]
        # 単一画像フィールドは付けない / order_id と variant を送る
        assert "image_data" not in body
        assert body["order_id"] == "md-1"
        assert body["variant"] == "clear"

    @pytest.mark.asyncio
    async def test_submit_single_image_uses_image_data(self) -> None:
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            captured["body"] = json.loads(request.content)
            return httpx.Response(202, json={"job_id": "job-2"})

        import base64

        await _client(handler).submit(
            product_type="tshirt",
            size="M",
            variant=None,
            input_mode="single",
            images={"design": b"\x89PNG-design"},
            order_id="md-2",
        )
        body = captured["body"]
        # 実VM: 単一画像モードは image_data + image_filename（images 配列は送らない）
        assert body["image_data"] == base64.b64encode(b"\x89PNG-design").decode()
        assert body["image_filename"]
        assert "images" not in body
        assert body["order_id"] == "md-2"

    @pytest.mark.asyncio
    async def test_submit_missing_job_id_raises(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(202, json={"unexpected": True})

        with pytest.raises(IllustratorVmError):
            await _client(handler).submit(
                product_type="tshirt",
                size="M",
                variant=None,
                input_mode="single",
                images={"design": b"x"},
            )

    @pytest.mark.asyncio
    async def test_submit_422_reads_detail(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(422, json={"detail": [{"msg": "bad size"}]})

        with pytest.raises(IllustratorVmError) as exc:
            await _client(handler).submit(
                product_type="tshirt",
                size="M",
                variant=None,
                input_mode="single",
                images={"design": b"x"},
            )
        assert "bad size" in str(exc.value)


class TestStatusAndWait:
    @pytest.mark.asyncio
    async def test_wait_polls_until_complete(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> Any:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(200, json={"status": "processing"})
            return httpx.Response(
                200, json={"status": "completed", "output_filename": "out.ai"}
            )

        status = await _client(handler).wait_until_complete("job-1")
        assert status.is_complete
        assert status.output_filename == "out.ai"
        assert calls["n"] == 3

    @pytest.mark.asyncio
    async def test_wait_raises_on_failed(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(200, json={"status": "failed", "error": "boom"})

        with pytest.raises(IllustratorVmError) as exc:
            await _client(handler).wait_until_complete("job-1")
        assert "boom" in str(exc.value)

    @pytest.mark.asyncio
    async def test_wait_times_out(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(200, json={"status": "processing"})

        client = IllustratorVmClient(
            "http://vm.test",
            poll_interval=0,
            max_poll_seconds=-1,  # 即タイムアウト
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(IllustratorVmError) as exc:
            await client.wait_until_complete("job-1")
        assert "timed out" in str(exc.value)


class TestDownloadAndRetry:
    @pytest.mark.asyncio
    async def test_download_returns_bytes(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(200, content=b"AI-FILE-BYTES")

        content = await _client(handler).download("job-1")
        assert content == b"AI-FILE-BYTES"

    @pytest.mark.asyncio
    async def test_503_is_retried_then_succeeds(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(503, json={"detail": "queue full"})
            return httpx.Response(200, content=b"OK")

        content = await _client(handler).download("job-1")
        assert content == b"OK"
        assert calls["n"] == 2

    @pytest.mark.asyncio
    async def test_transport_error_retried_then_raises(self) -> None:
        def handler(request: httpx.Request) -> None:
            raise httpx.ConnectError("refused")

        with pytest.raises(IllustratorVmError):
            await _client(handler).download("job-1")


class TestNonJsonResponse:
    @pytest.mark.asyncio
    async def test_non_json_2xx_is_retried_then_succeeds(self) -> None:
        # 2xx だが本文が JSON でない一過性応答はリトライ対象（生成を落とさない）。
        calls = {"n": 0}

        def handler(request: httpx.Request) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(200, text="<html>502 Bad Gateway</html>")
            return httpx.Response(
                200, json={"status": "completed", "output_filename": "o.ai"}
            )

        status = await _client(handler).get_status("job-1")
        assert status.status == "completed"
        assert calls["n"] == 2

    @pytest.mark.asyncio
    async def test_persistent_non_json_raises_illustrator_error(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(200, text="not json")

        with pytest.raises(IllustratorVmError):
            await _client(handler).get_status("job-1")


class TestUnavailableVsInputError:
    """VM に届かない失敗と、入力の誤りを型で分ける（呼び出し側が再試行可否を決める）."""

    @pytest.mark.asyncio
    async def test_connect_timeout_is_unavailable_and_names_the_exception(self) -> None:
        """ConnectTimeout は str() が空なので、型名を添えないと原因が読めない."""

        def handler(request: httpx.Request) -> None:
            raise httpx.ConnectTimeout("")

        with pytest.raises(IllustratorVmUnavailableError) as exc:
            await _client(handler).get_status("job-1")
        assert "ConnectTimeout" in str(exc.value)

    @pytest.mark.asyncio
    async def test_502_is_retried_then_unavailable(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> Any:
            calls["n"] += 1
            return httpx.Response(502, text="Bad Gateway")

        with pytest.raises(IllustratorVmUnavailableError):
            await _client(handler).get_status("job-1")
        assert calls["n"] == 3

    @pytest.mark.asyncio
    async def test_500_is_not_retried_nor_unavailable(self) -> None:
        """500 は VM が入力の処理中に落ちた可能性がある。何度投げても同じなので再試行しない."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> Any:
            calls["n"] += 1
            return httpx.Response(500, json={"detail": "boom"})

        with pytest.raises(IllustratorVmError) as exc:
            await _client(handler).get_status("job-1")
        assert not isinstance(exc.value, IllustratorVmUnavailableError)
        assert calls["n"] == 1

    @pytest.mark.asyncio
    async def test_422_is_an_input_error_not_unavailable(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(422, json={"detail": "bad size"})

        with pytest.raises(IllustratorVmError) as exc:
            await _client(handler).get_status("job-1")
        assert not isinstance(exc.value, IllustratorVmUnavailableError)

    @pytest.mark.asyncio
    async def test_failed_job_is_not_unavailable(self) -> None:
        """VM がジョブの失敗を報告したなら、VM には届いている。"""

        def handler(request: httpx.Request) -> Any:
            return httpx.Response(200, json={"status": "failed", "error": "boom"})

        with pytest.raises(IllustratorVmError) as exc:
            await _client(handler).wait_until_complete("job-1")
        assert not isinstance(exc.value, IllustratorVmUnavailableError)

    @pytest.mark.asyncio
    async def test_wait_timeout_is_unavailable(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(200, json={"status": "processing"})

        client = IllustratorVmClient(
            "http://vm.test",
            poll_interval=0,
            max_poll_seconds=-1,
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(IllustratorVmUnavailableError):
            await client.wait_until_complete("job-1")

    @pytest.mark.asyncio
    async def test_download_transport_error_is_unavailable(self) -> None:
        def handler(request: httpx.Request) -> None:
            raise httpx.ConnectError("refused")

        with pytest.raises(IllustratorVmUnavailableError) as exc:
            await _client(handler).download("job-1")
        assert "ConnectError" in str(exc.value)

    @pytest.mark.asyncio
    async def test_download_404_is_not_unavailable(self) -> None:
        def handler(request: httpx.Request) -> Any:
            return httpx.Response(404, json={"detail": "job not found"})

        with pytest.raises(IllustratorVmError) as exc:
            await _client(handler).download("job-1")
        assert not isinstance(exc.value, IllustratorVmUnavailableError)
        assert "job not found" in str(exc.value)


class TestHealth:
    @pytest.mark.asyncio
    async def test_healthy(self) -> None:
        def handler(request: httpx.Request) -> Any:
            assert request.url.path == "/health"
            return httpx.Response(200, json={"status": "healthy"})

        health = await _client(handler).health()
        assert health.ok

    @pytest.mark.asyncio
    async def test_503_unhealthy_is_ng(self) -> None:
        """応答はするが生成できない状態（ワーカー停止・ディスク不足）も NG."""

        def handler(request: httpx.Request) -> Any:
            return httpx.Response(503, json={"status": "unhealthy"})

        health = await _client(handler).health()
        assert not health.ok
        assert "503" in health.detail

    @pytest.mark.asyncio
    async def test_unreachable_is_ng_without_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> None:
            calls["n"] += 1
            raise httpx.ConnectTimeout("")

        health = await _client(handler).health()
        assert not health.ok
        assert health.detail == "ConnectTimeout"
        assert calls["n"] == 1  # 死活確認は 1 回で判断する（ワーカー起動を待たせない）


class TestFromSettings:
    def test_returns_none_when_unconfigured(self) -> None:
        from app.config import settings

        original = settings.ILLUSTRATOR_VM_BASE_URL
        settings.ILLUSTRATOR_VM_BASE_URL = ""
        try:
            assert IllustratorVmClient.from_settings(settings) is None
        finally:
            settings.ILLUSTRATOR_VM_BASE_URL = original

    def test_builds_client_when_configured(self) -> None:
        from app.config import settings

        original = settings.ILLUSTRATOR_VM_BASE_URL
        settings.ILLUSTRATOR_VM_BASE_URL = "http://vm.local:8000"
        try:
            client = IllustratorVmClient.from_settings(settings)
            assert isinstance(client, IllustratorVmClient)
        finally:
            settings.ILLUSTRATOR_VM_BASE_URL = original
