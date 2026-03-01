"""Base class for file format converters.

Provides common utility methods for table extraction, pagination,
and logging that subclasses can reuse.
"""

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BaseConverter(ABC):
    """Abstract base class for file format converters.

    Subclasses implement the `convert` method to transform a specific
    file format into Markdown. Common utilities like table formatting
    and pagination are provided as helper methods.

    Example:
        ```python
        class PDFConverter(BaseConverter):
            def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    return "\\n\\n".join(page.extract_text() or "" for page in pdf.pages)
        ```
    """

    @abstractmethod
    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        """Convert a file to Markdown format.

        Args:
            path: Path to the file to convert.
            raw_content: Optional pre-read content. For binary files,
                this will be bytes; for text files, it will be str.
                If None, the converter should read from path directly.

        Returns:
            Markdown-formatted string representation of the file content.
        """
        pass

    def supports_pagination(self) -> bool:
        """Check if this converter supports page-by-page reading.

        Returns:
            True if `convert_page` is implemented, False otherwise.
        """
        return False

    def convert_page(self, path: Path, page: int, raw_content: str | bytes | None = None) -> str:
        """Convert a single page to Markdown.

        Override this method and `supports_pagination` if the format
        supports efficient page extraction (e.g., PDF).

        Args:
            path: Path to the file.
            page: Page number (1-indexed).
            raw_content: Optional pre-read content.

        Returns:
            Markdown-formatted string for the requested page.

        Raises:
            NotImplementedError: If the converter doesn't support pagination.
            ValueError: If page number is out of range.
        """
        raise NotImplementedError("This converter does not support pagination")

    def get_total_pages(self, path: Path) -> int | None:
        """Get the total number of pages in the document.

        Override this method if the format supports pagination.

        Args:
            path: Path to the file.

        Returns:
            Total number of pages, or None if not supported.
        """
        return None

    def _format_as_table(self, rows: list[list[Any]], headers: list[str] | None = None) -> str:
        """Format a list of rows as a Markdown table.

        Args:
            rows: List of rows, where each row is a list of cell values.
            headers: Optional column headers.

        Returns:
            Markdown table string.
        """
        if not rows:
            return ""

        # Convert all cells to strings
        str_rows = [[str(cell) if cell is not None else "" for cell in row] for row in rows]

        # Use first row as headers if not provided
        if headers is None and str_rows:
            headers = str_rows[0]
            str_rows = str_rows[1:]
        elif headers is None:
            headers = []

        if not headers:
            return "\n".join(" ".join(row) for row in str_rows)

        # Calculate column widths
        all_rows = [headers] + str_rows
        col_widths = [
            max(len(row[i]) if i < len(row) else 0 for row in all_rows)
            for i in range(len(headers))
        ]

        # Build table
        lines = []

        # Header row
        header_cells = [h.ljust(w) for h, w in zip(headers, col_widths, strict=False)]
        lines.append("| " + " | ".join(header_cells) + " |")

        # Separator
        sep_cells = ["-" * w for w in col_widths]
        lines.append("| " + " | ".join(sep_cells) + " |")

        # Data rows
        for row in str_rows:
            cells = [
                (row[i] if i < len(row) else "").ljust(col_widths[i])
                for i in range(len(headers))
            ]
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def _log_conversion(self, path: Path, duration: float, *, page: int | None = None) -> None:
        """Log conversion completion with timing info.

        Args:
            path: Path to the converted file.
            duration: Time taken in seconds.
            page: Optional page number for paginated conversions.
        """
        page_info = f" (page {page})" if page else ""
        logger.info(f"Converted {path.name}{page_info} in {duration:.2f}s")

        if duration > 5.0:
            logger.warning(
                f"Conversion took {duration:.2f}s for {path.name}. "
                "Consider using pagination for large files."
            )