"""Unit tests for IllustratorVmClient (httpx mocked)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.illustrator_vm_client import IllustratorVmClient, IllustratorVmError

_PATCH = "app.services.illustrator_vm_client.httpx.AsyncClient"


def _resp(status_code, *, json_body=None, content=b""):
    r = MagicMock()
    r.status_code = status_code
    r.content = content
    r.text = ""
    if json_body is not None:
        r.json.return_value = json_body
    else:
        r.json.side_effect = ValueError("no json")
    return r


def _client_mock(*, response=None, responses=None):
    inst = AsyncMock()
    if responses is not None:
        inst.request.side_effect = responses
    else:
        inst.request.return_value = response
    inst.__aenter__ = AsyncMock(return_value=inst)
    inst.__aexit__ = AsyncMock(return_value=False)
    return inst


class TestSubmit:
    @pytest.mark.asyncio
    async def test_multi_image_payload(self):
        inst = _client_mock(response=_resp(202, json_body={"job_id": "job-1"}))
        client = IllustratorVmClient("http://vm:8000", poll_interval=0)
        with patch(_PATCH, return_value=inst):
            job_id = await client.submit(
                product_type="acrylic_keychain",
                vm_size="50x50",
                variant="clear",
                input_mode="multi",
                order_id="ORDER1",
                layers={"color": b"c", "cutline": b"l"},
            )
        assert job_id == "job-1"
        body = inst.request.call_args.kwargs["json"]
        assert body["size"] == "50x50"
        assert body["variant"] == "clear"
        assert {i["type"] for i in body["images"]} == {"color", "cutline"}

    @pytest.mark.asyncio
    async def test_single_image_payload(self):
        inst = _client_mock(response=_resp(202, json_body={"job_id": "job-2"}))
        client = IllustratorVmClient("http://vm:8000", poll_interval=0)
        with patch(_PATCH, return_value=inst):
            job_id = await client.submit(
                product_type="tshirt",
                vm_size="M",
                variant=None,
                input_mode="single",
                order_id="O1",
                layers={"design": b"d"},
            )
        assert job_id == "job-2"
        body = inst.request.call_args.kwargs["json"]
        assert "image_data" in body
        assert "images" not in body
        assert "variant" not in body

    @pytest.mark.asyncio
    async def test_4xx_raises_with_detail(self):
        inst = _client_mock(response=_resp(400, json_body={"detail": "bad size"}))
        client = IllustratorVmClient("http://vm:8000", poll_interval=0, max_retries=0)
        with patch(_PATCH, return_value=inst):
            with pytest.raises(IllustratorVmError) as exc:
                await client.submit(
                    product_type="tshirt",
                    vm_size="M",
                    variant=None,
                    input_mode="single",
                    order_id="O1",
                    layers={"design": b"d"},
                )
        assert "bad size" in str(exc.value)

    @pytest.mark.asyncio
    async def test_503_retries_then_succeeds(self):
        inst = _client_mock(
            responses=[
                _resp(503, json_body={"detail": "busy"}),
                _resp(202, json_body={"job_id": "job-3"}),
            ]
        )
        client = IllustratorVmClient("http://vm:8000", poll_interval=0, max_retries=2)
        with patch(_PATCH, return_value=inst):
            job_id = await client.submit(
                product_type="tshirt",
                vm_size="M",
                variant=None,
                input_mode="single",
                order_id="O1",
                layers={"design": b"d"},
            )
        assert job_id == "job-3"
        assert inst.request.call_count == 2


class TestStatusDownloadWait:
    @pytest.mark.asyncio
    async def test_get_status_parses(self):
        inst = _client_mock(
            response=_resp(
                200,
                json_body={
                    "job_id": "j",
                    "status": "completed",
                    "progress": 100,
                    "message": "ok",
                    "output_filename": "OUT.ai",
                },
            )
        )
        client = IllustratorVmClient("http://vm:8000", poll_interval=0)
        with patch(_PATCH, return_value=inst):
            st = await client.get_status("j")
        assert st.is_completed
        assert st.output_filename == "OUT.ai"

    @pytest.mark.asyncio
    async def test_download_returns_bytes(self):
        inst = _client_mock(response=_resp(200, content=b"AIDATA"))
        client = IllustratorVmClient("http://vm:8000", poll_interval=0)
        with patch(_PATCH, return_value=inst):
            assert await client.download("j") == b"AIDATA"

    @pytest.mark.asyncio
    async def test_wait_polls_until_completed(self):
        inst = _client_mock(
            responses=[
                _resp(200, json_body={"status": "processing", "progress": 50}),
                _resp(
                    200,
                    json_body={"status": "completed", "progress": 100, "output_filename": "O.ai"},
                ),
            ]
        )
        client = IllustratorVmClient("http://vm:8000", poll_interval=0, poll_timeout=1)
        with patch(_PATCH, return_value=inst):
            st = await client.wait_for_completion("j")
        assert st.is_completed
        assert inst.request.call_count == 2

    @pytest.mark.asyncio
    async def test_wait_failed_raises(self):
        inst = _client_mock(response=_resp(200, json_body={"status": "failed", "message": "boom"}))
        client = IllustratorVmClient("http://vm:8000", poll_interval=0, poll_timeout=1)
        with patch(_PATCH, return_value=inst):
            with pytest.raises(IllustratorVmError) as exc:
                await client.wait_for_completion("j")
        assert "boom" in str(exc.value)


class TestFromSettings:
    def test_returns_none_when_unset(self):
        # .env の ILLUSTRATOR_VM_URL は未設定 → None（生成機能オフ）
        assert IllustratorVmClient.from_settings() is None
