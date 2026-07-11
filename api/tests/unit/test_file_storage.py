"""Test file storage utilities."""

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound

from app.utils.file_storage import (
    GCSFileStorage,
    LocalFileStorage,
    build_file_storage,
    generate_stored_filename,
)


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


# ---------------------------------------------------------------------------
# GCSFileStorage
# ---------------------------------------------------------------------------


class _FakeBlob:
    """In-memory stand-in for a google.cloud.storage Blob."""

    def __init__(self, store: dict[str, bytes], name: str) -> None:
        self._store = store
        self._name = name

    def upload_from_string(self, data: bytes) -> None:
        self._store[self._name] = bytes(data)

    def download_as_bytes(self) -> bytes:
        if self._name not in self._store:
            raise NotFound(f"blob {self._name} not found")
        return self._store[self._name]

    def delete(self) -> None:
        if self._name not in self._store:
            raise NotFound(f"blob {self._name} not found")
        del self._store[self._name]

    def exists(self) -> bool:
        return self._name in self._store


class _FakeBucket:
    def __init__(self, store: dict[str, bytes]) -> None:
        self._store = store

    def blob(self, name: str) -> _FakeBlob:
        return _FakeBlob(self._store, name)


class _FakeGCSClient:
    """In-memory fake of google.cloud.storage.Client (no real GCS)."""

    def __init__(self) -> None:
        # bucket name -> {blob name: bytes}
        self.buckets: dict[str, dict[str, bytes]] = {}

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self.buckets.setdefault(name, {}))


def _mock_upload(filename: str, content: bytes) -> MagicMock:
    """Build a mock UploadFile matching FileStorage.save's expectations."""
    mock_file = MagicMock()
    mock_file.filename = filename
    mock_file.read = MagicMock(return_value=content)
    mock_file.seek = MagicMock()
    return mock_file


@pytest.fixture
def fake_gcs_client():
    """Fresh in-memory fake GCS client."""
    return _FakeGCSClient()


@pytest.fixture
def gcs_storage(fake_gcs_client):
    """GCSFileStorage backed by the fake client (bucket 'test-bucket')."""
    return GCSFileStorage(bucket="test-bucket", client=fake_gcs_client)


@pytest.mark.asyncio
async def test_gcs_save_and_get_roundtrip(gcs_storage, fake_gcs_client):
    """save() uploads to GCS and get() returns the same bytes."""
    content = b"manufacturing data .ai bytes"
    saved_path = await gcs_storage.save(_mock_upload("design.ai", content), "manufacturing_data/")

    # Backend-independent relative key (no leading prefix in the returned path).
    assert saved_path.startswith("manufacturing_data/")
    assert saved_path.endswith(".ai")

    # Stored under the same key inside the bucket (no GCS_PREFIX configured here).
    assert fake_gcs_client.buckets["test-bucket"][saved_path] == content

    # Round trip via get().
    assert await gcs_storage.get(saved_path) == content


@pytest.mark.asyncio
async def test_gcs_get_nonexistent_returns_none(gcs_storage):
    """get() returns None when the object does not exist."""
    assert await gcs_storage.get("manufacturing_data/missing.ai") is None


@pytest.mark.asyncio
async def test_gcs_delete(gcs_storage):
    """delete() removes an existing object and reports True."""
    saved_path = await gcs_storage.save(_mock_upload("a.pdf", b"pdf"), "shipments/1/")

    assert await gcs_storage.delete(saved_path) is True
    assert await gcs_storage.exists(saved_path) is False


@pytest.mark.asyncio
async def test_gcs_delete_nonexistent_returns_false(gcs_storage):
    """delete() returns False when the object is missing."""
    assert await gcs_storage.delete("chat/missing.png") is False


@pytest.mark.asyncio
async def test_gcs_exists(gcs_storage):
    """exists() reflects whether the object is present."""
    saved_path = await gcs_storage.save(_mock_upload("x.png", b"png"), "chat/")

    assert await gcs_storage.exists(saved_path) is True
    assert await gcs_storage.exists("chat/nope.png") is False


@pytest.mark.asyncio
async def test_gcs_prefix_is_prepended_to_object_name(fake_gcs_client):
    """GCS_PREFIX is prepended to the stored object name but not the returned key."""
    storage = GCSFileStorage(bucket="test-bucket", client=fake_gcs_client, prefix="prod")
    content = b"prefixed"

    saved_path = await storage.save(_mock_upload("f.ai", content), "manufacturing_data/")

    # Returned key stays namespace-free (DB.file_path is backend-independent).
    assert saved_path.startswith("manufacturing_data/")
    # Object is physically stored under the prefixed name.
    assert fake_gcs_client.buckets["test-bucket"][f"prod/{saved_path}"] == content
    # And the same relative key round-trips through get()/exists().
    assert await storage.get(saved_path) == content
    assert await storage.exists(saved_path) is True


# ---------------------------------------------------------------------------
# build_file_storage factory
# ---------------------------------------------------------------------------


def _settings(**overrides):
    """Minimal settings stub for the factory (duck-typed, no env required)."""
    base = {
        "UPLOAD_DIR": "uploads",
        "GCS_BUCKET": "",
        "GCS_CREDENTIALS_JSON": "",
        "GCS_PREFIX": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_factory_returns_local_when_no_bucket():
    """No GCS_BUCKET -> LocalFileStorage (default, behavior unchanged)."""
    storage = build_file_storage(_settings(UPLOAD_DIR="/data/uploads"))

    assert isinstance(storage, LocalFileStorage)
    assert storage.base_dir == "/data/uploads"


def test_factory_returns_gcs_when_bucket_set(monkeypatch):
    """GCS_BUCKET set -> GCSFileStorage, wired with bucket/prefix (no real client)."""
    fake_client = _FakeGCSClient()
    monkeypatch.setattr(
        "app.utils.file_storage._build_gcs_client", lambda credentials_json: fake_client
    )

    storage = build_file_storage(_settings(GCS_BUCKET="my-bucket", GCS_PREFIX="prod"))

    assert isinstance(storage, GCSFileStorage)
    assert storage._bucket_name == "my-bucket"
    assert storage._prefix == "prod"
    assert storage._client is fake_client


def test_gcs_client_is_cached_per_process(monkeypatch):
    """_build_gcs_client reuses one client (no per-request rebuild/auth)."""
    import google.cloud.storage as gcs_storage

    from app.utils import file_storage

    constructed: list[object] = []

    def _fake_client_ctor(*args, **kwargs):
        client = object()
        constructed.append(client)
        return client

    monkeypatch.setattr(gcs_storage, "Client", _fake_client_ctor)
    file_storage._build_gcs_client.cache_clear()
    try:
        first = file_storage._build_gcs_client("")
        second = file_storage._build_gcs_client("")
        assert first is second  # same client reused
        assert len(constructed) == 1  # constructed exactly once
    finally:
        file_storage._build_gcs_client.cache_clear()


# ---------------------------------------------------------------------------
# generate_stored_filename helper
# ---------------------------------------------------------------------------


def test_generate_stored_filename_preserves_extension():
    """The generated name keeps the original extension."""
    assert generate_stored_filename("photo.PNG").endswith(".PNG")
    assert generate_stored_filename("archive.tar.gz").endswith(".gz")


def test_generate_stored_filename_without_extension():
    """A name without an extension yields a bare timestamp_uuid."""
    name = generate_stored_filename(None)
    assert "." not in name
    # timestamp(15 chars: YYYYMMDD_HHMMSS) + "_" + uuid8
    assert len(name.split("_")) == 3


def test_generate_stored_filename_is_unique():
    """Two calls produce distinct names (uuid component)."""
    assert generate_stored_filename("a.pdf") != generate_stored_filename("a.pdf")
