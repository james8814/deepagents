"""Converter registry for mapping MIME types to converters."""

import logging
from typing import TypeAlias
import importlib

from deepagents.middleware.converters.base import BaseConverter

logger = logging.getLogger(__name__)

# Type alias for the registry
ConverterRegistry: TypeAlias = dict[str, BaseConverter]


def _create_default_registry() -> ConverterRegistry:
    """Create the default converter registry with lazy loading.

    This function creates converters on-demand to avoid import errors
    when optional dependencies are not installed.

    Returns:
        Dictionary mapping MIME types to converter instances.
    """
    registry: ConverterRegistry = {}

    # Text converter (always available, no dependencies)
    text_mod = importlib.import_module("deepagents.middleware.converters.text")
    TextConverter = getattr(text_mod, "TextConverter")
    text_converter = TextConverter()
    registry["text/plain"] = text_converter
    registry["text/markdown"] = text_converter
    registry["text/x-python"] = text_converter
    registry["text/javascript"] = text_converter
    registry["text/typescript"] = text_converter
    registry["text/x-java"] = text_converter
    registry["text/x-c"] = text_converter
    registry["text/x-c++"] = text_converter
    registry["text/x-rust"] = text_converter
    registry["text/x-go"] = text_converter
    registry["text/x-ruby"] = text_converter
    registry["text/x-php"] = text_converter
    registry["text/x-shellscript"] = text_converter
    registry["application/json"] = text_converter
    registry["application/xml"] = text_converter
    registry["application/x-yaml"] = text_converter
    registry["application/x-sql"] = text_converter

    # PDF converter (optional: pdfplumber)
    try:
        pdf_mod = importlib.import_module("deepagents.middleware.converters.pdf")
        PDFConverter = getattr(pdf_mod, "PDFConverter")
        pdf_converter = PDFConverter()
        registry["application/pdf"] = pdf_converter
    except ImportError:
        logger.debug("PDF converter not available (install pdfplumber)")

    # CSV converter (no dependencies beyond stdlib)
    csv_mod = importlib.import_module("deepagents.middleware.converters.csv")
    CSVConverter = getattr(csv_mod, "CSVConverter")
    csv_converter = CSVConverter()
    registry["text/csv"] = csv_converter

    # Excel converter (optional: openpyxl)
    try:
        xlsx_mod = importlib.import_module("deepagents.middleware.converters.xlsx")
        XLSXConverter = getattr(xlsx_mod, "XLSXConverter")
        xlsx_converter = XLSXConverter()
        registry["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"] = xlsx_converter
        registry["application/vnd.ms-excel"] = xlsx_converter
    except ImportError:
        logger.debug("XLSX converter not available (install openpyxl)")

    # Word converter (optional: python-docx)
    try:
        docx_mod = importlib.import_module("deepagents.middleware.converters.docx")
        DOCXConverter = getattr(docx_mod, "DOCXConverter")
        docx_converter = DOCXConverter()
        registry["application/vnd.openxmlformats-officedocument.wordprocessingml.document"] = docx_converter
        registry["application/msword"] = docx_converter
    except ImportError:
        logger.debug("DOCX converter not available (install python-docx)")

    # PowerPoint converter (optional: python-pptx)
    try:
        pptx_mod = importlib.import_module("deepagents.middleware.converters.pptx")
        PPTXConverter = getattr(pptx_mod, "PPTXConverter")
        pptx_converter = PPTXConverter()
        registry["application/vnd.openxmlformats-officedocument.presentationml.presentation"] = pptx_converter
        registry["application/vnd.ms-powerpoint"] = pptx_converter
    except ImportError:
        logger.debug("PPTX converter not available (install python-pptx)")

    # Image converter (basic placeholder support)
    image_mod = importlib.import_module("deepagents.middleware.converters.image")
    ImageConverter = getattr(image_mod, "ImageConverter")
    image_converter = ImageConverter()
    registry["image/png"] = image_converter
    registry["image/jpeg"] = image_converter
    registry["image/gif"] = image_converter
    registry["image/webp"] = image_converter
    registry["image/svg+xml"] = image_converter

    return registry


# Lazy-loaded default registry
_DEFAULT_REGISTRY: ConverterRegistry | None = None


def get_default_registry() -> ConverterRegistry:
    """Get the default converter registry (lazy initialization).

    Returns:
        The default converter registry.
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _create_default_registry()
    return _DEFAULT_REGISTRY


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
