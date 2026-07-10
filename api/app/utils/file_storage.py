"""File storage utilities.

`FileStorage` を抽象化し、ローカル（開発）と GCS（本番=Railway）を切り替える。

- ローカル: `LocalFileStorage`。`UPLOAD_DIR` 配下に保存。
- GCS: `GCSFileStorage`。公式 `google-cloud-storage`（同期）を `asyncio.to_thread`
  でラップしてイベントループを塞がない。`GCS_PREFIX` を内部で前置するため、DB に持つ
  `file_path`（＝ save が返す相対キー）はバックエンド非依存で共通。
- 生成先は `build_file_storage(settings)` に集約。`GCS_BUCKET` があれば GCS、無ければ
  ローカル（既定・挙動不変）。
"""

from __future__ import annotations

import asyncio
import json
import os
import posixpath
from abc import ABC, abstractmethod
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

import aiofiles
import aiofiles.os

if TYPE_CHECKING:
    from app.config import Settings


class UploadFile(Protocol):
    """Protocol for uploaded file objects."""

    filename: str | None

    def read(self) -> bytes: ...
    def seek(self, offset: int) -> None: ...


def generate_stored_filename(original_filename: str | None) -> str:
    """保存用の一意なファイル名を生成する（拡張子は元ファイルから保持）.

    Local/GCS で同一命名を使うため、モジュール関数として共通化する。
    書式: ``{timestamp}_{uuid8}{ext}``（例: ``20260710_121530_1a2b3c4d.pdf``）。
    """
    ext = os.path.splitext(original_filename)[1] if original_filename else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid4())[:8]
    return f"{timestamp}_{unique_id}{ext}"


async def _read_upload(file: UploadFile) -> bytes:
    """UploadFile から内容を読む（同期/非同期の read 両対応）."""
    content = file.read()
    if hasattr(content, "__await__"):
        content = await content
    return content


class FileStorage(ABC):
    """Abstract base class for file storage."""

    @abstractmethod
    async def save(self, file: UploadFile, prefix: str = "") -> str:
        """Save a file and return the path."""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a file. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    async def get(self, path: str) -> bytes | None:
        """Get file content. Returns None if not found."""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass


class LocalFileStorage(FileStorage):
    """Local filesystem storage implementation."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def _get_full_path(self, path: str) -> str:
        """Get the full filesystem path."""
        return os.path.join(self.base_dir, path)

    async def save(self, file: UploadFile, prefix: str = "") -> str:
        """Save a file and return the relative path."""
        filename = generate_stored_filename(file.filename)
        relative_path = os.path.join(prefix, filename)
        full_path = self._get_full_path(relative_path)

        # Create directory if it doesn't exist
        dir_path = os.path.dirname(full_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        content = await _read_upload(file)

        # Write file
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)

        return relative_path

    async def delete(self, path: str) -> bool:
        """Delete a file. Returns True if deleted, False if not found."""
        full_path = self._get_full_path(path)
        try:
            await aiofiles.os.remove(full_path)
            return True
        except FileNotFoundError:
            return False

    async def get(self, path: str) -> bytes | None:
        """Get file content. Returns None if not found."""
        full_path = self._get_full_path(path)
        try:
            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        except FileNotFoundError:
            return None

    async def exists(self, path: str) -> bool:
        """Check if a file exists."""
        full_path = self._get_full_path(path)
        return await aiofiles.os.path.exists(full_path)


class GCSFileStorage(FileStorage):
    """Google Cloud Storage storage implementation.

    公式 `google-cloud-storage`（同期API）を `asyncio.to_thread` でラップし、
    イベントループを塞がずに使う。`save` が返す相対キーは Local と共通（DBの
    `file_path` は非依存）で、GCS のオブジェクト名は内部で `prefix`（`GCS_PREFIX`）
    を前置して構成する。

    `client` を注入可能にしてテストを実 GCS 非依存にする（フェイククライアント）。
    """

    def __init__(self, bucket: str, client: Any, prefix: str = ""):
        self._bucket_name = bucket
        self._client = client
        # 名前空間プレフィックス。余分な区切りを正規化してキー結合を安定させる。
        self._prefix = prefix.strip("/")

    def _blob_name(self, path: str) -> str:
        """相対キーを GCS オブジェクト名（prefix 前置）に変換する."""
        key = path.strip("/")
        return f"{self._prefix}/{key}" if self._prefix else key

    def _get_blob(self, path: str) -> Any:
        """対象 blob ハンドルを返す（同期。to_thread から呼ぶ）."""
        bucket = self._client.bucket(self._bucket_name)
        return bucket.blob(self._blob_name(path))

    async def save(self, file: UploadFile, prefix: str = "") -> str:
        """Save a file and return the backend-independent relative path."""
        filename = generate_stored_filename(file.filename)
        # 相対キーは POSIX 区切りで統一（GCS キーは常に "/" 区切り）。
        relative_path = posixpath.join(prefix, filename)
        content = await _read_upload(file)

        def _upload() -> None:
            self._get_blob(relative_path).upload_from_string(content)

        await asyncio.to_thread(_upload)
        return relative_path

    async def delete(self, path: str) -> bool:
        """Delete a file. Returns True if deleted, False if not found."""
        from google.api_core.exceptions import NotFound

        def _delete() -> bool:
            try:
                self._get_blob(path).delete()
                return True
            except NotFound:
                return False

        return await asyncio.to_thread(_delete)

    async def get(self, path: str) -> bytes | None:
        """Get file content. Returns None if not found."""
        from google.api_core.exceptions import NotFound

        def _download() -> bytes | None:
            try:
                data: bytes = self._get_blob(path).download_as_bytes()
            except NotFound:
                return None
            return data

        return await asyncio.to_thread(_download)

    async def exists(self, path: str) -> bool:
        """Check if a file exists."""

        def _exists() -> bool:
            return bool(self._get_blob(path).exists())

        return await asyncio.to_thread(_exists)


@lru_cache(maxsize=1)
def _build_gcs_client(credentials_json: str) -> Any:
    """GCS クライアントを構築する（プロセス内で1つを再利用）.

    `storage.Client` は生成コスト（認証・コネクションプール確立）が高く再利用が推奨
    されるため、認証情報をキーにキャッシュする。`credentials_json`（SA鍵JSON文字列）
    があればそれで認証し、空なら ADC（ローカル/GCE のデフォルト認証）へフォールバックする。
    """
    from google.cloud import storage

    if credentials_json:
        info = json.loads(credentials_json)
        return storage.Client.from_service_account_info(info)
    return storage.Client()


def build_file_storage(settings: Settings) -> FileStorage:
    """設定に応じて FileStorage 実装を返す単一ファクトリ.

    `GCS_BUCKET` があれば GCS、無ければローカル（既定・挙動不変）。
    """
    if settings.GCS_BUCKET:
        return GCSFileStorage(
            bucket=settings.GCS_BUCKET,
            client=_build_gcs_client(settings.GCS_CREDENTIALS_JSON),
            prefix=settings.GCS_PREFIX,
        )
    return LocalFileStorage(settings.UPLOAD_DIR)
