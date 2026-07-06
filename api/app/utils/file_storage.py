"""File storage utilities."""

import asyncio
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import uuid4

import aiofiles
import aiofiles.os


class UploadFile(Protocol):
    """Protocol for uploaded file objects."""

    filename: str | None

    def read(self) -> bytes: ...
    def seek(self, offset: int) -> None: ...


class BytesUpload:
    """UploadFile プロトコル互換の bytes ラッパー.

    生成済みの製造データなど、既に手元にある bytes を FileStorage.save() で保存する用。
    """

    def __init__(self, content: bytes, filename: str | None = None) -> None:
        self._content = content
        self.filename = filename

    def read(self) -> bytes:
        return self._content

    def seek(self, offset: int) -> None:
        return None


def _generate_stored_filename(original_filename: str | None) -> str:
    """拡張子を保持したユニークな保存ファイル名を生成する。"""
    ext = os.path.splitext(original_filename)[1] if original_filename else ""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid4())[:8]
    return f"{timestamp}_{unique_id}{ext}"


async def _read_upload(file: UploadFile) -> bytes:
    """UploadFile の内容を読む（Starlette の UploadFile.read() は coroutine なので両対応）。"""
    result: Any = file.read()
    if hasattr(result, "__await__"):
        result = await result
    return cast(bytes, result)


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

    def _generate_filename(self, original_filename: str | None) -> str:
        """Generate a unique filename preserving the extension."""
        return _generate_stored_filename(original_filename)

    async def save(self, file: UploadFile, prefix: str = "") -> str:
        """Save a file and return the relative path."""
        filename = self._generate_filename(file.filename)
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
    """Google Cloud Storage backend（Cloud Run のディスク揮発を回避し永続保存する）.

    google-cloud-storage は遅延importするため、STORAGE_BACKEND=local の環境では
    パッケージ未導入でも本モジュールを読み込める。同期SDKは asyncio.to_thread で実行。
    """

    def __init__(self, bucket_name: str, project: str | None = None) -> None:
        from google.cloud import storage  # type: ignore[attr-defined]

        self.bucket_name = bucket_name
        client = storage.Client(project=project) if project else storage.Client()
        self._bucket = client.bucket(bucket_name)

    async def save(self, file: UploadFile, prefix: str = "") -> str:
        key = os.path.join(prefix, _generate_stored_filename(file.filename))
        content = await _read_upload(file)
        blob = self._bucket.blob(key)
        await asyncio.to_thread(blob.upload_from_string, content)
        return key

    async def delete(self, path: str) -> bool:
        from google.cloud.exceptions import NotFound

        blob = self._bucket.blob(path)
        try:
            await asyncio.to_thread(blob.delete)
            return True
        except NotFound:
            return False

    async def get(self, path: str) -> bytes | None:
        from google.cloud.exceptions import NotFound

        blob = self._bucket.blob(path)
        try:
            return cast(bytes, await asyncio.to_thread(blob.download_as_bytes))
        except NotFound:
            return None

    async def exists(self, path: str) -> bool:
        blob = self._bucket.blob(path)
        return bool(await asyncio.to_thread(blob.exists))


def build_file_storage() -> FileStorage:
    """設定に応じた FileStorage 実装を返す（DI とバックグラウンドワーカー共通のファクトリ）。"""
    from app.config import settings

    if settings.STORAGE_BACKEND == "gcs" and settings.GCS_BUCKET:
        return GCSFileStorage(settings.GCS_BUCKET, project=settings.GCS_PROJECT or None)
    return LocalFileStorage(settings.UPLOAD_DIR)
