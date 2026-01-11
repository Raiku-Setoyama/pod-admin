"""ZIP file building utilities."""

import io
import zipfile
from datetime import datetime


class ZipBuilder:
    """ZIP file builder for purchase order documents."""

    def __init__(self):
        self._buffer = io.BytesIO()
        self._zip = zipfile.ZipFile(self._buffer, "w", zipfile.ZIP_DEFLATED)

    def add_file(self, filename: str, content: bytes) -> None:
        """Add a file to the ZIP archive."""
        self._zip.writestr(filename, content)

    def add_excel(self, filename: str, content: bytes) -> None:
        """Add an Excel file to the ZIP archive."""
        self.add_file(filename, content)

    def add_csv(self, filename: str, content: bytes) -> None:
        """Add a CSV file to the ZIP archive."""
        self.add_file(filename, content)

    def add_manufacturing_data(self, filename: str, content: bytes) -> None:
        """Add manufacturing data file to the ZIP archive."""
        self.add_file(f"製造データ/{filename}", content)

    def build(self) -> bytes:
        """Finalize and return the ZIP file content."""
        self._zip.close()
        self._buffer.seek(0)
        return self._buffer.getvalue()

    @staticmethod
    def create_directory_name(manufacturer_name: str, order_date: datetime) -> str:
        """Create directory name in format [メーカー名][日付]発注分."""
        date_str = order_date.strftime("%Y%m%d")
        return f"{manufacturer_name}{date_str}発注分"
