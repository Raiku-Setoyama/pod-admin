"""TOSYO DRIVE client for file uploads."""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class DriveUploadResult:
    """Result of a DRIVE upload operation."""

    def __init__(
        self,
        success: bool,
        file_id: str | None = None,
        url: str | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.file_id = file_id
        self.url = url
        self.error = error


class DriveClient(ABC):
    """Abstract base class for DRIVE client implementations."""

    @abstractmethod
    async def upload(
        self,
        content: bytes,
        filename: str,
        folder_path: str,
    ) -> DriveUploadResult:
        """Upload a file to DRIVE.

        Args:
            content: File content as bytes
            filename: Name of the file
            folder_path: Path to the folder in DRIVE

        Returns:
            DriveUploadResult with upload status
        """
        pass

    @abstractmethod
    async def check_connection(self) -> bool:
        """Check if connection to DRIVE is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        pass


class MockDriveClient(DriveClient):
    """Mock DRIVE client for development and testing.

    This implementation simulates DRIVE uploads without actually
    connecting to any external service. Use TosyoDriveClient
    for production when API specifications are available.
    """

    async def upload(
        self,
        content: bytes,
        filename: str,
        folder_path: str,
    ) -> DriveUploadResult:
        """Simulate a file upload to DRIVE."""
        logger.info(f"[Mock] Uploading {filename} to {folder_path}")
        logger.info(f"[Mock] File size: {len(content)} bytes")

        # Simulate successful upload
        return DriveUploadResult(
            success=True,
            file_id=f"mock-{filename}",
            url=f"https://drive.tosyo.example/files/mock-{filename}",
        )

    async def check_connection(self) -> bool:
        """Always return True for mock client."""
        return True


class TosyoDriveClient(DriveClient):
    """Production TOSYO DRIVE client.

    TODO: Implement when TOSYO DRIVE API specifications are available.
    Currently falls back to mock implementation.
    """

    def __init__(self, api_url: str, api_key: str):
        self._api_url = api_url
        self._api_key = api_key
        logger.warning(
            "TosyoDriveClient is not yet implemented. "
            "Using mock behavior until API specs are available."
        )

    async def upload(
        self,
        content: bytes,
        filename: str,
        folder_path: str,
    ) -> DriveUploadResult:
        """Upload a file to TOSYO DRIVE.

        TODO: Implement actual API call when specs are available.
        """
        logger.info(f"Would upload {filename} to {folder_path} on TOSYO DRIVE")

        # For now, simulate success
        return DriveUploadResult(
            success=True,
            file_id=f"tosyo-{filename}",
            url=f"{self._api_url}/files/tosyo-{filename}",
        )

    async def check_connection(self) -> bool:
        """Check connection to TOSYO DRIVE.

        TODO: Implement actual health check when specs are available.
        """
        return True


def get_drive_client(
    api_url: str | None = None,
    api_key: str | None = None,
) -> DriveClient:
    """Factory function to get appropriate DRIVE client.

    Args:
        api_url: TOSYO DRIVE API URL (if None, uses mock client)
        api_key: TOSYO DRIVE API key (if None, uses mock client)

    Returns:
        DriveClient instance
    """
    if api_url and api_key:
        return TosyoDriveClient(api_url, api_key)
    return MockDriveClient()
