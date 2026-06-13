"""Stand file configuration for acrylic figure products.

Provides size-based mapping for stand template files stored under
app/static/stand_templates/.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory where stand template .ai files are stored
# Resolved relative to this file: app/utils/../../static/stand_templates
STAND_TEMPLATES_DIR: Path = Path(__file__).resolve().parent.parent / "static" / "stand_templates"

# Size -> filename mapping
STAND_FILE_MAPPING: dict[str, str] = {
    "50x50mm": "アクリルフィギュアスタンド_50mm_台座.ai",
    "70x70mm": "アクリルフィギュアスタンド_70mm_台座.ai",
    "100x100mm": "アクリルフィギュアスタンド_100mm_台座.ai",
}

# Default filename (used when size is not in STAND_FILE_MAPPING)
DEFAULT_STAND_FILENAME: str = "アクリルフィギュアスタンド_70mm_台座.ai"


def get_stand_file_path(size: str | None = None) -> Path:
    """Get the full path to the stand template file for the given size.

    Args:
        size: Product size string (e.g. "70x70mm"). If None, returns default.

    Returns:
        Full path to the stand template file.
    """
    filename = DEFAULT_STAND_FILENAME if size is None else STAND_FILE_MAPPING.get(size, DEFAULT_STAND_FILENAME)
    return STAND_TEMPLATES_DIR / filename


def load_stand_file(size: str | None = None) -> bytes | None:
    """Load the stand template file content for the given size.

    Args:
        size: Product size string (e.g. "70x70mm"). If None, uses default.

    Returns:
        File content as bytes, or None if the file does not exist.
    """
    path = get_stand_file_path(size)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        logger.warning("Stand template file not found: %s", path)
        return None
