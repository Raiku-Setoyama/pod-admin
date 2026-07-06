"""Unit tests for GCSFileStorage and build_file_storage (google-cloud-storage mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from app.utils.file_storage import (
    BytesUpload,
    GCSFileStorage,
    LocalFileStorage,
    build_file_storage,
)


def _mock_client():
    """Return (client_mock, blob_mock) wired as Client().bucket().blob()."""
    blob = MagicMock()
    bucket = MagicMock()
    bucket.blob.return_value = blob
    client = MagicMock()
    client.bucket.return_value = bucket
    return client, blob


class TestGCSFileStorage:
    @pytest.mark.asyncio
    async def test_save_uploads_and_returns_key(self):
        client, blob = _mock_client()
        with patch("google.cloud.storage.Client", return_value=client):
            storage = GCSFileStorage("my-bucket")
            key = await storage.save(BytesUpload(b"AIDATA", "out.ai"), prefix="manufacturing")
        assert key.startswith("manufacturing/")
        assert key.endswith(".ai")
        blob.upload_from_string.assert_called_once_with(b"AIDATA")

    @pytest.mark.asyncio
    async def test_get_returns_bytes(self):
        client, blob = _mock_client()
        blob.download_as_bytes.return_value = b"CONTENT"
        with patch("google.cloud.storage.Client", return_value=client):
            storage = GCSFileStorage("my-bucket")
            data = await storage.get("manufacturing/x.ai")
        assert data == b"CONTENT"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        from google.cloud.exceptions import NotFound

        client, blob = _mock_client()
        blob.download_as_bytes.side_effect = NotFound("missing")
        with patch("google.cloud.storage.Client", return_value=client):
            storage = GCSFileStorage("my-bucket")
            data = await storage.get("manufacturing/x.ai")
        assert data is None

    @pytest.mark.asyncio
    async def test_exists_true(self):
        client, blob = _mock_client()
        blob.exists.return_value = True
        with patch("google.cloud.storage.Client", return_value=client):
            storage = GCSFileStorage("my-bucket")
            assert await storage.exists("manufacturing/x.ai") is True

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self):
        from google.cloud.exceptions import NotFound

        client, blob = _mock_client()
        blob.delete.side_effect = NotFound("missing")
        with patch("google.cloud.storage.Client", return_value=client):
            storage = GCSFileStorage("my-bucket")
            assert await storage.delete("manufacturing/x.ai") is False


class TestBuildFileStorage:
    def test_local_by_default(self):
        # 既定 settings は STORAGE_BACKEND=local
        assert isinstance(build_file_storage(), LocalFileStorage)
