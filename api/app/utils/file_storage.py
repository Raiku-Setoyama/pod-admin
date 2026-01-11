"""File storage utilities."""

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol
from uuid import uuid4

import aiofiles
import aiofiles.os


class UploadFile(Protocol):
    """Protocol for uploaded file objects."""

    filename: str | None

    def read(self) -> bytes: ...
    def seek(self, offset: int) -> None: ...


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
        if original_filename:
            _, ext = os.path.splitext(original_filename)
        else:
            ext = ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid4())[:8]
        return f"{timestamp}_{unique_id}{ext}"

    async def save(self, file: UploadFile, prefix: str = "") -> str:
        """Save a file and return the relative path."""
        filename = self._generate_filename(file.filename)
        relative_path = os.path.join(prefix, filename)
        full_path = self._get_full_path(relative_path)

        # Create directory if it doesn't exist
        dir_path = os.path.dirname(full_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # Read content (handle both sync and async)
        content = file.read()
        if hasattr(content, "__await__"):
            content = await content

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
