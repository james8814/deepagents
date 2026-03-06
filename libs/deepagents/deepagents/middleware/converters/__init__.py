"""File format converters for the unified file reader.

This package provides converters that transform various file formats
(PDF, DOCX, XLSX, etc.) into Markdown format for LLM consumption.

Example:
    ```python
    from deepagents.middleware.converters import DEFAULT_CONVERTER_REGISTRY, detect_mime_type

    # Detect file type
    mime_type = detect_mime_type("/uploads/report.pdf")

    # Get converter from registry
    converter = DEFAULT_CONVERTER_REGISTRY.get(mime_type)

    # Convert to Markdown
    markdown = converter.convert(Path("/uploads/report.pdf"))
    ```
"""

from deepagents.middleware.converters.base import BaseConverter
from deepagents.middleware.converters.registry import (
    DEFAULT_CONVERTER_REGISTRY,
    ConverterRegistry,
    ConverterRegistryManager,
    get_default_registry,
)
from deepagents.middleware.converters.utils import detect_mime_type

__all__ = [
    "DEFAULT_CONVERTER_REGISTRY",
    "BaseConverter",
    "ConverterRegistry",
    "ConverterRegistryManager",
    "detect_mime_type",
    "get_default_registry",
]
