"""Word document converter using python-docx."""

import importlib
import logging
import time
from pathlib import Path
from typing import Protocol

from deepagents.middleware.converters.base import BaseConverter

logger = logging.getLogger(__name__)
HEADING_PREFIXES = {
    "heading 1": "#",
    "heading 2": "##",
    "heading 3": "###",
    "heading 4": "####",
    "heading 5": "#####",
    "heading 6": "######",
}


class _ParagraphStyle(Protocol):
    name: str


class _Paragraph(Protocol):
    text: str
    style: _ParagraphStyle | None


class _TableCell(Protocol):
    text: str


class _TableRow(Protocol):
    cells: list[_TableCell]


class _Table(Protocol):
    rows: list[_TableRow]


class DOCXConverter(BaseConverter):
    """Converter for Word documents to Markdown.

    Supports .docx files with:
    - Text and paragraphs
    - Headings and styles
    - Tables
    - Lists

    Dependencies:
        python-docx: Install with `pip install python-docx`
    """

    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        """Convert a Word document to Markdown.

        Args:
            path: Path to the Word document.
            raw_content: Ignored for Word documents (binary format).

        Returns:
            Markdown-formatted string.
        """
        _ = raw_content
        try:
            document_factory = importlib.import_module("docx").Document
        except ModuleNotFoundError as e:
            msg = "Missing optional dependency `python-docx`. Install with `pip install python-docx`."
            raise ModuleNotFoundError(msg) from e

        start = time.time()

        doc = document_factory(str(path))
        parts = []

        for para in doc.paragraphs:
            formatted_paragraph = self._format_paragraph(para)
            if formatted_paragraph:
                parts.append(formatted_paragraph)

        # Extract tables
        for i, table in enumerate(doc.tables, start=1):
            parts.append(f"\n### Table {i}\n")
            rows = self._extract_table_rows(table)

            if rows:
                headers = rows[0]
                data_rows = rows[1:] if len(rows) > 1 else []
                parts.append(self._format_as_table(data_rows, headers))

        duration = time.time() - start
        self._log_conversion(path, duration)

        return "\n\n".join(parts)

    def _format_paragraph(self, para: _Paragraph) -> str:
        text = para.text.strip()
        if not text:
            return ""

        style_name = para.style.name.lower() if para.style else ""
        for heading_name, prefix in HEADING_PREFIXES.items():
            if heading_name in style_name:
                return f"{prefix} {text}\n"

        if "list" in style_name:
            return f"- {text}"
        return text

    def _extract_table_rows(self, table: _Table) -> list[list[str]]:
        return [[cell.text.strip() for cell in row.cells] for row in table.rows]
