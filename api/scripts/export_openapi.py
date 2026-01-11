#!/usr/bin/env python3
"""Export OpenAPI schema from FastAPI application."""

import json
import sys
from pathlib import Path

import yaml

# Add the api directory to the path
api_dir = Path(__file__).parent.parent
sys.path.insert(0, str(api_dir))

from app.main import app  # noqa: E402


def export_openapi_schema(output_path: Path, format: str = "yaml") -> None:
    """Export OpenAPI schema to file.

    Args:
        output_path: Path to output file
        format: Output format, either 'yaml' or 'json'
    """
    schema = app.openapi()

    if format == "yaml":
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(schema, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)

    print(f"OpenAPI schema exported to {output_path}")


if __name__ == "__main__":
    # Default output path
    output_path = Path(__file__).parent.parent.parent / "openapi" / "schema.yaml"

    # Check for command line arguments
    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1])

    # Determine format from file extension
    format = "json" if output_path.suffix == ".json" else "yaml"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_openapi_schema(output_path, format)
