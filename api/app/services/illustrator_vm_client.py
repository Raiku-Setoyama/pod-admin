"""illustrator-vm（Product Manufacturing API）クライアント.

非同期ジョブ型の外部 API を叩いて製造データ（.ai/.pdf）を生成する。

  POST /api/process        (base64 PNG 入力, 202 + job_id)
  GET  /api/status/{job_id}(ポーリング)
  GET  /api/download/{job_id}(ファイル取得)

特性（呼び出し側で吸収する）:
- 認証なし / CORS * / 既定 127.0.0.1:8000（プライベートVM前提）
- 直列処理（1件ずつ・最大約300秒）。キュー上限50超で 503。
- 完了ジョブ・出力ファイルは 72時間でハード削除 → 速やかに DL・自前保存が必須。
- order_id は一意ではない（冪等性は呼び出し側の責務）。
- バリデーションエラーは 422（`{"detail": [...]}`）。エラーは `detail` を参照。
- 出力ファイル名は status の `output_filename` を正とする。
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.utils.exceptions import TransientDependencyError

logger = logging.getLogger(__name__)

# VM が完了・失敗を示すステータス値（表記ゆれを吸収）
_COMPLETE_STATUSES = {"completed", "complete", "done", "success", "succeeded", "finished"}
_FAILED_STATUSES = {"failed", "error", "errored", "cancelled", "canceled"}


class IllustratorVmError(Exception):
    """illustrator-vm 呼び出しに関するエラー."""


class IllustratorVmUnavailableError(IllustratorVmError, TransientDependencyError):
    """VM に届かない・応答しないエラー（**入力ではなく VM 側の都合**）.

    接続できない・タイムアウト・502/503/504（キュー満杯・前段の不調）・完了待ちの打ち切りが該当する。
    同じ入力で後から再試行すれば成功しうるので、呼び出し側は製造データを failed に
    確定させず、生成待ちへ戻して VM の復旧を待つ。

    422 などの 4xx（入力の誤り）、500（VM が入力の処理中に落ちた可能性がある）、
    VM がジョブの失敗を報告した場合は
    親クラスの IllustratorVmError のまま投げる。何度やり直しても結果が変わらないため。

    ``TransientDependencyError`` も継がせてあるのは、**生成待ちへ戻す判断を依存先ごとに
    書き分けないため**である。VM だけでなく GCS や元データの配信元が一時的に落ちた場合も
    同じ扱いが要る（manufacturing_data_service はこの型 1 つだけを見る）。
    """


# 接続確立だけのタイムアウト（秒）。応答待ちより短くする。
# VM が止まると SYN が黙って捨てられ（Windows のファイアウォールは閉じたポートに
# 応答しない）、応答待ちと同じ 60 秒を接続だけで使い切ってしまうため。
_CONNECT_TIMEOUT = 10.0

# 死活確認（/health）のタイムアウト（秒）。VM の /health は同期的に tasklist を
# 走らせるため数秒かかることがある。
_HEALTH_TIMEOUT = 20.0


# 一時的とみなす（再試行し、尽きたら「VM に届かない」とする）5xx。
# それ以外の 5xx（500 など）は VM 側で入力を処理して落ちた可能性があり、
# 何度投げても同じなので再試行しない。
_TRANSIENT_STATUSES = frozenset({502, 503, 504})


def _describe(exc: BaseException | None) -> str:
    """例外を「型名: メッセージ」で表す.

    httpx の ConnectTimeout などは str() が空文字になるため、型名を添えないと
    「VM POST /api/process failed: 」のように原因が読めないエラー文になる。
    """
    if exc is None:
        return ""
    message = str(exc)
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


@dataclass
class VmHealth:
    """死活確認（GET /health）の結果."""

    ok: bool
    detail: str


@dataclass
class VmJobStatus:
    """ジョブのステータス（status エンドポイント由来）."""

    job_id: str
    status: str
    output_filename: str | None = None
    error: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.status.lower() in _COMPLETE_STATUSES

    @property
    def is_failed(self) -> bool:
        return self.status.lower() in _FAILED_STATUSES


class IllustratorVmClient:
    """illustrator-vm の submit / status / download をラップするクライアント."""

    def __init__(
        self,
        base_url: str,
        *,
        auth_header: str | None = None,
        request_timeout: float = 60.0,
        poll_interval: float = 5.0,
        max_poll_seconds: float = 360.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        self._base_url = base_url.rstrip("/")
        self._auth_header = auth_header or None
        self._request_timeout = request_timeout
        self._poll_interval = poll_interval
        self._max_poll_seconds = max_poll_seconds
        self._max_retries = max(1, max_retries)
        # テスト用に httpx transport を注入可能（本番は None = 既定トランスポート）
        self._transport = transport

    def _new_client(self, timeout: float | None = None) -> httpx.AsyncClient:
        total = timeout if timeout is not None else self._request_timeout
        return httpx.AsyncClient(
            timeout=httpx.Timeout(total, connect=min(_CONNECT_TIMEOUT, total)),
            transport=self._transport,
        )

    @classmethod
    def from_settings(cls, settings: Any) -> IllustratorVmClient | None:
        """Settings から生成。未設定（base_url 空）なら None を返す."""
        if not settings.ILLUSTRATOR_VM_BASE_URL:
            return None
        return cls(
            settings.ILLUSTRATOR_VM_BASE_URL,
            auth_header=settings.ILLUSTRATOR_VM_AUTH_HEADER or None,
            request_timeout=settings.ILLUSTRATOR_VM_REQUEST_TIMEOUT,
            poll_interval=settings.ILLUSTRATOR_VM_POLL_INTERVAL,
            max_poll_seconds=settings.ILLUSTRATOR_VM_MAX_POLL_SECONDS,
            max_retries=settings.ILLUSTRATOR_VM_MAX_RETRIES,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._auth_header:
            headers["Authorization"] = self._auth_header
        return headers

    async def health(self) -> VmHealth:
        """VM の死活を 1 回だけ確認する（リトライしない）.

        ``status == "healthy"`` の 200 応答だけを生存とみなす。VM の /health は
        ワーカー停止やディスク不足のとき 503 を返す（応答はするが生成できない）。
        """
        try:
            async with self._new_client(timeout=_HEALTH_TIMEOUT) as client:
                response = await client.get(f"{self._base_url}/health", headers=self._headers())
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            return VmHealth(ok=False, detail=_describe(exc))
        try:
            body = response.json()
        except ValueError:
            body = {}
        status = body.get("status") if isinstance(body, dict) else None
        if response.status_code == 200 and status == "healthy":
            return VmHealth(ok=True, detail="healthy")
        return VmHealth(ok=False, detail=f"HTTP {response.status_code} status={status}")

    async def submit(
        self,
        *,
        product_type: str,
        size: str,
        variant: str | None,
        input_mode: str,
        images: dict[str, bytes],
        order_id: str | None = None,
    ) -> str:
        """製造データ生成ジョブを投入し、job_id を返す.

        images は {layer_type: PNGバイト列}。VM の ProcessRequest 形式に整形して送る:
        - 単一画像モード(single): image_data(base64) + image_filename
        - 複数画像モード(multi):  images = [{type, data(base64), filename}, ...]
        """
        if not images:
            raise IllustratorVmError("at least one source image is required")

        # order_id は VM の必須フィールド（string）。呼び出し側が未指定なら空文字で満たす。
        payload: dict[str, object] = {
            "product_type": product_type,
            "size": size,
            "variant": variant,
            "order_id": order_id or "",
        }

        if input_mode == "single":
            # 単一画像商品(tshirt/tote): 1枚を image_data として送る。
            layer, content = self._pick_single_image(images)
            payload["image_data"] = base64.b64encode(content).decode("ascii")
            payload["image_filename"] = f"{layer}.png"
        else:
            # 複数画像商品(keychain/stand/sticker): ImageInput の配列。
            payload["images"] = [
                {
                    "type": layer,
                    "data": base64.b64encode(content).decode("ascii"),
                    "filename": f"{layer}.png",
                }
                for layer, content in images.items()
            ]

        data = await self._request_json("POST", "/api/process", json=payload)
        job_id = data.get("job_id") or data.get("id")
        if not job_id:
            raise IllustratorVmError(f"submit response missing job_id: {data}")
        return str(job_id)

    @staticmethod
    def _pick_single_image(images: dict[str, bytes]) -> tuple[str, bytes]:
        """単一画像モードで送る1枚を決める（design 優先、次に color、無ければ任意）."""
        for preferred in ("design", "color"):
            if preferred in images:
                return preferred, images[preferred]
        return next(iter(images.items()))

    async def get_status(self, job_id: str) -> VmJobStatus:
        """ジョブの現在ステータスを取得する."""
        data = await self._request_json("GET", f"/api/status/{job_id}")
        status = str(data.get("status") or "").strip() or "unknown"
        error = data.get("error")
        if error is None:
            # VM のエラーは detail に入ることがある
            detail = data.get("detail")
            error = detail if isinstance(detail, str) else None
        return VmJobStatus(
            job_id=job_id,
            status=status,
            output_filename=data.get("output_filename"),
            error=error,
        )

    async def wait_until_complete(self, job_id: str) -> VmJobStatus:
        """完了/失敗するまでステータスをポーリングする.

        Raises:
            IllustratorVmError: ジョブが失敗した、またはタイムアウトした場合。
        """
        deadline = time.monotonic() + self._max_poll_seconds
        last_status: VmJobStatus | None = None
        while True:
            last_status = await self.get_status(job_id)
            if last_status.is_complete:
                return last_status
            if last_status.is_failed:
                raise IllustratorVmError(
                    f"VM job {job_id} failed: {last_status.error or last_status.status}"
                )
            if time.monotonic() >= deadline:
                # VM が詰まっている（直列処理の前のジョブが終わらない等）。入力の問題ではない。
                raise IllustratorVmUnavailableError(
                    f"VM job {job_id} timed out after {self._max_poll_seconds}s "
                    f"(last status: {last_status.status})"
                )
            await asyncio.sleep(self._poll_interval)

    async def download(self, job_id: str) -> bytes:
        """生成済みファイルのバイト列を取得する."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                async with self._new_client() as client:
                    response = await client.get(
                        f"{self._base_url}/api/download/{job_id}",
                        headers=self._headers(),
                    )
                if response.status_code in _TRANSIENT_STATUSES:
                    last_exc = IllustratorVmError(
                        f"VM returned {response.status_code} while downloading"
                    )
                    await self._backoff(attempt)
                    continue
                if response.status_code >= 400:
                    # 404・500 など。完了済みジョブの出力が無い・VM が落ちたのは
                    # 待っても変わらない。
                    raise IllustratorVmError(
                        f"VM GET /api/download/{job_id} -> {response.status_code}: "
                        f"{_extract_error(response)}"
                    )
                return response.content
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                await self._backoff(attempt)
        raise IllustratorVmUnavailableError(
            f"failed to download VM job {job_id}: {_describe(last_exc)}"
        ) from last_exc

    async def _request_json(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        """JSON を返すエンドポイントを叩く（ネットワークエラー・503 は簡易リトライ）."""
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                async with self._new_client() as client:
                    response = await client.request(
                        method, url, json=json, headers=self._headers()
                    )
                if response.status_code in _TRANSIENT_STATUSES:
                    # 503 はキュー満杯、502/504 は前段の一時的な不調。
                    last_exc = IllustratorVmError(
                        f"VM {method} {path} -> {response.status_code}: "
                        f"{_extract_error(response)}"
                    )
                    await self._backoff(attempt)
                    continue
                if response.status_code >= 400:
                    raise IllustratorVmError(
                        f"VM {method} {path} -> {response.status_code}: "
                        f"{_extract_error(response)}"
                    )
                try:
                    body: dict[str, Any] = response.json()
                    return body
                except ValueError:
                    # 2xx だが本文が JSON でない（前段 proxy の一時的な HTML/空応答など）。
                    # 一過性のことが多いためリトライ対象として扱う（未捕捉で生成を
                    # 落とさない）。
                    last_exc = IllustratorVmError(
                        f"VM {method} {path} returned a non-JSON body: "
                        f"{response.text[:200]!r}"
                    )
                    await self._backoff(attempt)
                    continue
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                await self._backoff(attempt)
        raise IllustratorVmUnavailableError(
            f"VM {method} {path} failed: {_describe(last_exc)}"
        ) from last_exc

    async def _backoff(self, attempt: int) -> None:
        # 1s, 2s, 4s, ... （最終試行後は待たない）
        if attempt < self._max_retries - 1:
            await asyncio.sleep(2**attempt)


def _extract_error(response: httpx.Response) -> str:
    """VM のエラーレスポンスから `detail` を抽出する（error ではない）."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    detail = body.get("detail")
    if detail is not None:
        return str(detail)
    return str(body)[:500]
