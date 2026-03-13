"""File format converters for the unified file reader.

This package provides converters that transform various file formats
(PDF, DOCX, XLSX, etc.) into Markdown format for LLM consumption.

Example:
    ```python
    from pathlib import Path
    from deepagents.middleware.converters import get_default_registry, detect_mime_type

    mime_type = detect_mime_type("/uploads/report.pdf")
    registry = get_default_registry()
    converter = registry.get(mime_type)
    if converter:
        markdown = converter.convert(Path("/uploads/report.pdf"))
    ```
"""

from deepagents.middleware.converters.base import BaseConverter
from deepagents.middleware.converters.registry import (
    ConverterRegistry,
    ConverterRegistryManager,
    get_default_registry,
)
from deepagents.middleware.converters.utils import detect_mime_type

__all__ = [
    "BaseConverter",
    "ConverterRegistry",
    "ConverterRegistryManager",
    "detect_mime_type",
    "get_default_registry",
]
