"""Client for the illustrator-vm Product Manufacturing API.

illustrator-vm は製造データ（.ai/.pdf）を生成する非同期ジョブ型API（認証なし）。
    POST /api/process        -> 202 {job_id, status, ...}
    GET  /api/status/{job_id} -> 200 {status, progress, output_filename, message, ...}
    GET  /api/download/{job_id} -> 200 ファイルbytes
直列処理（Illustrator 1インスタンス, 最大~300秒）・キュー超過で 503・完了は72hでGC。
冪等性は呼び出し側の責務。出力ファイル名は status の output_filename を正とする。
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# 生成完了とみなす/失敗とみなす status 値
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"


class IllustratorVmError(Exception):
    """illustrator-vm 呼び出しに関するエラー（サービス層が捕捉して failed 記録に使う）."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class VmJobStatus:
    """GET /api/status のレスポンス（必要フィールドのみ）."""

    job_id: str
    status: str
    progress: int
    message: str | None
    output_filename: str | None

    @property
    def is_completed(self) -> bool:
        return self.status == _STATUS_COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == _STATUS_FAILED


class IllustratorVmClient:
    """illustrator-vm への薄いHTTPクライアント（submit / status / download / 待機）."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
        poll_timeout: float = 360.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._max_retries = max(0, max_retries)

    @classmethod
    def from_settings(cls) -> IllustratorVmClient | None:
        """設定から生成。ILLUSTRATOR_VM_URL 未設定なら None（生成機能オフ）."""
        from app.config import settings

        if not settings.ILLUSTRATOR_VM_URL:
            return None
        return cls(
            base_url=settings.ILLUSTRATOR_VM_URL,
            timeout=settings.ILLUSTRATOR_VM_TIMEOUT,
            poll_interval=settings.ILLUSTRATOR_VM_POLL_INTERVAL,
            poll_timeout=settings.ILLUSTRATOR_VM_POLL_TIMEOUT,
            max_retries=settings.ILLUSTRATOR_VM_MAX_RETRIES,
        )

    async def submit(
        self,
        *,
        product_type: str,
        vm_size: str,
        variant: str | None,
        input_mode: str,
        order_id: str,
        layers: dict[str, bytes],
        filenames: dict[str, str] | None = None,
    ) -> str:
        """POST /api/process。ジョブを投入し job_id を返す。

        layers は「レイヤー種別 -> PNG bytes」。single モードは design（無ければ唯一の
        レイヤー）を image_data に、multi モードは images 配列に載せる。
        """
        names = filenames or {}
        payload: dict[str, object] = {
            "product_type": product_type,
            "order_id": order_id,
            "size": vm_size,
        }
        if variant:
            payload["variant"] = variant

        if input_mode == "single":
            if not layers:
                raise IllustratorVmError("single モードには元画像が1枚必要です")
            design_bytes = layers.get("design") or next(iter(layers.values()))
            payload["image_data"] = base64.b64encode(design_bytes).decode()
            payload["image_filename"] = names.get("design", "design.png")
        else:
            payload["images"] = [
                {
                    "type": layer_type,
                    "data": base64.b64encode(data).decode(),
                    "filename": names.get(layer_type, f"{layer_type}.png"),
                }
                for layer_type, data in layers.items()
            ]

        response = await self._request_with_retry("POST", "/api/process", json=payload)
        data = response.json()
        job_id = data.get("job_id")
        if not job_id:
            raise IllustratorVmError("submit のレスポンスに job_id がありません")
        return str(job_id)

    async def get_status(self, job_id: str) -> VmJobStatus:
        """GET /api/status/{job_id}。"""
        response = await self._request_with_retry("GET", f"/api/status/{job_id}")
        data = response.json()
        return VmJobStatus(
            job_id=str(data.get("job_id", job_id)),
            status=str(data.get("status", "")),
            progress=int(data.get("progress", 0) or 0),
            message=data.get("message"),
            output_filename=data.get("output_filename"),
        )

    async def download(self, job_id: str) -> bytes:
        """GET /api/download/{job_id}。完成ファイルの bytes を返す。"""
        response = await self._request_with_retry("GET", f"/api/download/{job_id}")
        return response.content

    async def wait_for_completion(self, job_id: str) -> VmJobStatus:
        """completed になるまで status をポーリングする。

        failed は IllustratorVmError、poll_timeout 超過も IllustratorVmError。
        """
        # poll_interval=0（テスト等）でも複数回ポーリングできるよう下限intervalで回数を決める
        interval = self._poll_interval if self._poll_interval > 0 else 0.001
        max_polls = max(1, int(self._poll_timeout / interval))
        last_status: VmJobStatus | None = None
        for attempt in range(max_polls):
            status = await self.get_status(job_id)
            last_status = status
            if status.is_completed:
                return status
            if status.is_failed:
                raise IllustratorVmError(
                    f"illustrator-vm ジョブが失敗しました: {status.message or 'unknown error'}"
                )
            if attempt < max_polls - 1:
                await asyncio.sleep(self._poll_interval)

        raise IllustratorVmError(
            f"illustrator-vm ジョブが {self._poll_timeout} 秒以内に完了しませんでした"
            f"（最終status: {last_status.status if last_status else 'unknown'}）"
        )

    async def _request_with_retry(
        self, method: str, path: str, *, json: dict[str, object] | None = None
    ) -> httpx.Response:
        """503/一時的な接続エラーはバックオフ再送。4xx は即エラー（入力不正）。"""
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(method, url, json=json)
                if response.status_code == 503:
                    last_exc = IllustratorVmError(
                        "illustrator-vm がビジー状態です (503)", status_code=503
                    )
                elif response.status_code >= 400:
                    raise IllustratorVmError(
                        f"illustrator-vm がエラーを返しました ({response.status_code}): "
                        f"{_extract_detail(response)}",
                        status_code=response.status_code,
                    )
                else:
                    return response
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc

            if attempt < self._max_retries:
                await asyncio.sleep(self._poll_interval)

        raise IllustratorVmError(f"illustrator-vm への {method} {path} が失敗しました: {last_exc}")


def _extract_detail(response: httpx.Response) -> str:
    """エラーレスポンスから detail を取り出す（illustrator-vm は error ではなく detail を使う）。"""
    try:
        body = response.json()
    except Exception:
        return response.text[:200]
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return str(body)[:200]
