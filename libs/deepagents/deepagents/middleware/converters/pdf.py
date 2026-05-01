"""PDF file converter using pdfplumber."""

import importlib
import logging
import time
from pathlib import Path

from deepagents.middleware.converters.base import BaseConverter

logger = logging.getLogger(__name__)


class PDFConverter(BaseConverter):
    """Converter for PDF files to Markdown format.

    Uses pdfplumber for text extraction with support for:
    - Multi-page documents
    - Table extraction
    - Page-by-page reading

    Dependencies:
        pdfplumber: Install with `pip install pdfplumber`
    """

    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        """Convert a PDF file to Markdown.

        Args:
            path: Path to the PDF file.
            raw_content: Ignored for PDF files (binary format).

        Returns:
            Markdown-formatted string with all pages.
        """
        _ = raw_content
        try:
            pdfplumber = importlib.import_module("pdfplumber")
        except ModuleNotFoundError as e:
            msg = "Missing optional dependency `pdfplumber`. Install with `pip install pdfplumber`."
            raise ModuleNotFoundError(msg) from e

        start = time.time()
        parts = []

        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract text
                text = page.extract_text() or ""

                # Extract tables if present
                tables = page.extract_tables()

                page_parts = [f"## Page {page_num}/{total_pages}\n"]

                if text.strip():
                    page_parts.append(text.strip())

                # Add tables as markdown tables
                for table_num, table in enumerate(tables, start=1):
                    if table and len(table) > 0:
                        page_parts.append(f"\n### Table {table_num} (Page {page_num})\n")
                        page_parts.append(self._format_table(table))

                parts.append("\n".join(page_parts))

        duration = time.time() - start
        self._log_conversion(path, duration)

        return "\n\n---\n\n".join(parts)

    def supports_pagination(self) -> bool:
        """PDF supports page-by-page reading.

        Returns:
            True
        """
        return True

    def convert_page(self, path: Path, page: int, raw_content: str | bytes | None = None) -> str:
        """Convert a single page to Markdown.

        Args:
            path: Path to the PDF file.
            page: Page number (1-indexed).
            raw_content: Ignored for PDF files.

        Returns:
            Markdown-formatted string for the requested page.

        Raises:
            ValueError: If page number is out of range.
        """
        _ = raw_content
        try:
            pdfplumber = importlib.import_module("pdfplumber")
        except ModuleNotFoundError as e:
            msg = "Missing optional dependency `pdfplumber`. Install with `pip install pdfplumber`."
            raise ModuleNotFoundError(msg) from e

        start = time.time()

        with pdfplumber.open(path) as pdf:
            total_pages = len(pdf.pages)

            if page < 1 or page > total_pages:
                msg = f"Page {page} out of range. Document has {total_pages} pages."
                raise ValueError(msg)

            pdf_page = pdf.pages[page - 1]
            text = pdf_page.extract_text() or ""
            tables = pdf_page.extract_tables()

            parts = [f"## Page {page}/{total_pages}\n"]

            if text.strip():
                parts.append(text.strip())

            # Add tables
            for table_num, table in enumerate(tables, start=1):
                if table and len(table) > 0:
                    parts.append(f"\n### Table {table_num}\n")
                    parts.append(self._format_table(table))

        duration = time.time() - start
        self._log_conversion(path, duration, page=page)

        return "\n".join(parts)

    def get_total_pages(self, path: Path) -> int:
        """Get total number of pages in the PDF.

        Args:
            path: Path to the PDF file.

        Returns:
            Total number of pages.
        """
        try:
            pdfplumber = importlib.import_module("pdfplumber")
        except ModuleNotFoundError as e:
            msg = "Missing optional dependency `pdfplumber`. Install with `pip install pdfplumber`."
            raise ModuleNotFoundError(msg) from e

        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)

    def _format_table(self, table: list[list[str | None]]) -> str:
        """Format a table as Markdown.

        Args:
            table: 2D list of table cells.

        Returns:
            Markdown table string.
        """
        if not table or not table[0]:
            return ""

        # Clean up cells
        rows = []
        for row in table:
            clean_row = [str(cell).strip() if cell else "" for cell in row]
            rows.append(clean_row)

        # Use first row as headers
        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []

        return self._format_as_table(data_rows, headers)
