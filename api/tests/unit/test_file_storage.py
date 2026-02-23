"""Test file storage utilities."""

import os
import tempfile
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from app.utils.file_storage import LocalFileStorage


@pytest.fixture
def temp_upload_dir():
    """Create a temporary directory for uploads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def file_storage(temp_upload_dir):
    """Create a LocalFileStorage instance with temp directory."""
    return LocalFileStorage(temp_upload_dir)


@pytest.mark.asyncio
async def test_save_file(file_storage, temp_upload_dir):
    """Test saving a file."""
    # Create a mock UploadFile
    content = b"test file content"
    mock_file = MagicMock()
    mock_file.filename = "test.png"
    mock_file.read = MagicMock(return_value=content)
    mock_file.seek = MagicMock()

    # Save the file
    saved_path = await file_storage.save(mock_file, "orders/123/")

    # Verify path format
    assert saved_path.startswith("orders/123/")
    assert saved_path.endswith(".png")

    # Verify file exists
    full_path = os.path.join(temp_upload_dir, saved_path)
    assert os.path.exists(full_path)

    # Verify content
    with open(full_path, "rb") as f:
        assert f.read() == content


@pytest.mark.asyncio
async def test_save_file_creates_directory(file_storage, temp_upload_dir):
    """Test that save creates necessary directories."""
    mock_file = MagicMock()
    mock_file.filename = "test.pdf"
    mock_file.read = MagicMock(return_value=b"content")
    mock_file.seek = MagicMock()

    saved_path = await file_storage.save(mock_file, "new/nested/path/")

    full_path = os.path.join(temp_upload_dir, saved_path)
    assert os.path.exists(full_path)


@pytest.mark.asyncio
async def test_delete_file(file_storage, temp_upload_dir):
    """Test deleting a file."""
    # Create a file first
    test_path = "test/file.txt"
    full_path = os.path.join(temp_upload_dir, test_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write("test")

    # Delete the file
    result = await file_storage.delete(test_path)

    assert result is True
    assert not os.path.exists(full_path)


@pytest.mark.asyncio
async def test_delete_nonexistent_file(file_storage):
    """Test deleting a nonexistent file returns False."""
    result = await file_storage.delete("nonexistent/file.txt")
    assert result is False


@pytest.mark.asyncio
async def test_get_file(file_storage, temp_upload_dir):
    """Test getting file content."""
    # Create a file first
    test_path = "test/file.txt"
    content = b"test content"
    full_path = os.path.join(temp_upload_dir, test_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(content)

    # Get the file
    result = await file_storage.get(test_path)

    assert result == content


@pytest.mark.asyncio
async def test_get_nonexistent_file(file_storage):
    """Test getting a nonexistent file returns None."""
    result = await file_storage.get("nonexistent/file.txt")
    assert result is None


@pytest.mark.asyncio
async def test_exists(file_storage, temp_upload_dir):
    """Test checking file existence."""
    # Create a file
    test_path = "test/exists.txt"
    full_path = os.path.join(temp_upload_dir, test_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write("test")

    assert await file_storage.exists(test_path) is True
    assert await file_storage.exists("nonexistent.txt") is False
