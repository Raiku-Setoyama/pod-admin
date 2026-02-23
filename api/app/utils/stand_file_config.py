"""Stand file configuration for acrylic figure products.

Provides size-based mapping for stand template files.
Extensible: add size → file path entries to STAND_FILE_MAPPING to
support different stand templates per product size.
"""

# Size -> stand file path mapping
# Currently all sizes use the same default file. Add entries here
# to differentiate by size (e.g. "50x50mm": "/path/to/50mm_stand.ai").
STAND_FILE_MAPPING: dict[str, str] = {
    "50x50mm": "【サンプル】アクリルフィギュアスタンド_50mm_台座.ai",
    "70x70mm": "【サンプル】アクリルフィギュアスタンド_70mm_台座.ai",
    "100x100mm": "【サンプル】アクリルフィギュアスタンド_100mm_台座.ai",
    "160x160mm": "【サンプル】アクリルフィギュアスタンド_160mm_台座.ai",
}

# Default stand file path (used when size is not in STAND_FILE_MAPPING)
DEFAULT_STAND_FILE_PATH: str = "【サンプル】アクリルフィギュアスタンド_70mm_台座.ai"


def get_stand_file_path(size: str | None = None) -> str:
    """Get the stand file path for the given size.

    Args:
        size: Product size string (e.g. "70x70mm"). If None, returns default.

    Returns:
        File path to the stand template file.
    """
    if size is None:
        return DEFAULT_STAND_FILE_PATH
    return STAND_FILE_MAPPING.get(size, DEFAULT_STAND_FILE_PATH)
