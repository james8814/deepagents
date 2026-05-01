"""Converter registry for mapping MIME types to converters."""

import importlib
import logging
from functools import lru_cache

from deepagents.middleware.converters.base import BaseConverter

logger = logging.getLogger(__name__)

ConverterRegistry = dict[str, BaseConverter]

TEXT_MIME_TYPES = (
    "text/plain",
    "text/markdown",
    "text/x-python",
    "text/javascript",
    "text/typescript",
    "text/x-java",
    "text/x-c",
    "text/x-c++",
    "text/x-rust",
    "text/x-go",
    "text/x-ruby",
    "text/x-php",
    "text/x-shellscript",
    "application/json",
    "application/xml",
    "application/x-yaml",
    "application/x-sql",
)


def _load_converter(module_name: str, class_name: str) -> BaseConverter:
    module = importlib.import_module(module_name)
    converter_cls = getattr(module, class_name)
    return converter_cls()


def _register_shared_converter(registry: ConverterRegistry, mime_types: tuple[str, ...], converter: BaseConverter) -> None:
    for mime_type in mime_types:
        registry[mime_type] = converter


def _try_register_optional_converter(
    registry: ConverterRegistry,
    mime_types: tuple[str, ...],
    module_name: str,
    class_name: str,
    message: str,
) -> None:
    try:
        converter = _load_converter(module_name, class_name)
    except ImportError:
        logger.debug(message)
        return

    _register_shared_converter(registry, mime_types, converter)


def _create_default_registry() -> ConverterRegistry:
    """Create the default converter registry with lazy loading.

    This function creates converters on-demand to avoid import errors
    when optional dependencies are not installed.

    Returns:
        Dictionary mapping MIME types to converter instances.
    """
    registry: ConverterRegistry = {}

    # Text converter (always available, no dependencies)
    text_converter = _load_converter("deepagents.middleware.converters.text", "TextConverter")
    _register_shared_converter(registry, TEXT_MIME_TYPES, text_converter)

    # CSV converter (no dependencies beyond stdlib)
    registry["text/csv"] = _load_converter("deepagents.middleware.converters.csv", "CSVConverter")

    _try_register_optional_converter(
        registry,
        ("application/pdf",),
        "deepagents.middleware.converters.pdf",
        "PDFConverter",
        "PDF converter not available (install pdfplumber)",
    )
    _try_register_optional_converter(
        registry,
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ),
        "deepagents.middleware.converters.xlsx",
        "XLSXConverter",
        "XLSX converter not available (install openpyxl)",
    )
    _try_register_optional_converter(
        registry,
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ),
        "deepagents.middleware.converters.docx",
        "DOCXConverter",
        "DOCX converter not available (install python-docx)",
    )
    _try_register_optional_converter(
        registry,
        (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        ),
        "deepagents.middleware.converters.pptx",
        "PPTXConverter",
        "PPTX converter not available (install python-pptx)",
    )

    # Image converter (basic placeholder support)
    image_converter = _load_converter("deepagents.middleware.converters.image", "ImageConverter")
    _register_shared_converter(
        registry,
        ("image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"),
        image_converter,
    )

    return registry


@lru_cache(maxsize=1)
def get_default_registry() -> ConverterRegistry:
    """Get the default converter registry (lazy initialization).

    Returns:
        The default converter registry.
    """
    return _create_default_registry()


class ConverterRegistryManager:
    """Manager for converter registry with support for custom converters.

    Example:
        ```python
        from deepagents.middleware.converters import ConverterRegistryManager

        # Use default registry
        manager = ConverterRegistryManager()

        # Get converter for a MIME type
        converter = manager.get_converter("application/pdf")

        # Register a custom converter
        manager.register("application/x-myformat", MyConverter())
        ```
    """

    def __init__(self, custom_registry: ConverterRegistry | None = None) -> None:
        """Initialize the registry manager.

        Args:
            custom_registry: Optional custom registry to use instead of default.
                If provided, it will be used as-is without the default converters.
        """
        self._custom_registry = custom_registry
        self._overrides: ConverterRegistry = {}

    def get_converter(self, mime_type: str) -> BaseConverter | None:
        """Get a converter for the given MIME type.

        Args:
            mime_type: The MIME type to get a converter for.

        Returns:
            Converter instance, or None if no converter is registered.
        """
        # Check overrides first
        if mime_type in self._overrides:
            return self._overrides[mime_type]

        # Use custom registry or default
        registry = self._custom_registry or get_default_registry()
        return registry.get(mime_type)

    def register(self, mime_type: str, converter: BaseConverter) -> None:
        """Register a converter for a MIME type.

        Args:
            mime_type: The MIME type to register for.
            converter: The converter instance.
        """
        self._overrides[mime_type] = converter

    def unregister(self, mime_type: str) -> bool:
        """Unregister a converter for a MIME type.

        Args:
            mime_type: The MIME type to unregister.

        Returns:
            True if a converter was removed, False otherwise.
        """
        if mime_type in self._overrides:
            del self._overrides[mime_type]
            return True
        return False

    def get_supported_types(self) -> list[str]:
        """Get list of supported MIME types.

        Returns:
            List of MIME types that have registered converters.
        """
        registry = self._custom_registry or get_default_registry()
        types = set(registry.keys())
        types.update(self._overrides.keys())
        return sorted(types)
