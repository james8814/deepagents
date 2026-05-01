"""Image file converter with placeholder support."""

import importlib
import logging
import time
from pathlib import Path
from typing import ClassVar

from deepagents.middleware.converters.base import BaseConverter

logger = logging.getLogger(__name__)

# Size constants
KB = 1024
MB = 1024 * KB


class ImageConverter(BaseConverter):
    """Converter for image files to placeholder Markdown.

    Provides basic metadata about images without attempting to display
    binary content. Returns a placeholder message with file information.

    Note:
        For actual image analysis, use the `execute` tool with appropriate
        image processing commands or external tools.
    """

    # Supported image extensions
    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}

    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        """Convert an image file to a placeholder Markdown.

        Args:
            path: Path to the image file.
            raw_content: Ignored for image files (binary format).

        Returns:
            Markdown-formatted placeholder with image metadata.
        """
        _ = raw_content
        start = time.time()

        if not path.exists():
            return f"(Image file not found: {path})"

        # Get basic file info
        try:
            stat = path.stat()
            file_size = stat.st_size
        except OSError:
            file_size = 0

        # Format file size
        if file_size < KB:
            size_str = f"{file_size} bytes"
        elif file_size < MB:
            size_str = f"{file_size / KB:.1f} KB"
        else:
            size_str = f"{file_size / MB:.1f} MB"

        # Try to get image dimensions with PIL (optional)
        dimensions = "Unknown"
        format_name = path.suffix.upper().lstrip(".")

        try:
            image_module = importlib.import_module("PIL.Image")

            with image_module.open(path) as img:
                width, height = img.size
                dimensions = f"{width} x {height} pixels"
                if img.format:
                    format_name = img.format
        except ModuleNotFoundError:
            logger.debug("PIL not installed, skipping image dimensions")
        except (AttributeError, OSError, TypeError, ValueError) as exc:
            logger.debug("Could not read image dimensions: %s", exc)

        duration = time.time() - start
        self._log_conversion(path, duration)

        # Build placeholder message
        lines = [
            f"## Image: {path.name}",
            "",
            "**File Information:**",
            f"- **Path**: `{path}`",
            f"- **Format**: {format_name}",
            f"- **Dimensions**: {dimensions}",
            f"- **Size**: {size_str}",
            "",
            "**Note**: This is an image file. Binary content is not displayed.",
            "To work with this image, use the `execute` tool with appropriate commands.",
        ]

        return "\n".join(lines)
