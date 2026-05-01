"""PowerPoint presentation converter using python-pptx."""

import importlib
import logging
import time
from collections.abc import Sized
from pathlib import Path
from typing import Protocol

from deepagents.middleware.converters.base import BaseConverter

logger = logging.getLogger(__name__)
TITLE_FONT_SIZE_PT = 24


class _SlideTable(Protocol):
    rows: Sized
    columns: Sized

    def cell(self, row_idx: int, col_idx: int) -> "_SlideCell": ...


class _SlideCell(Protocol):
    text: str


class PPTXConverter(BaseConverter):
    """Converter for PowerPoint presentations to Markdown.

    Supports .pptx files with:
    - Slide-by-slide extraction
    - Text and shape extraction
    - Tables

    Dependencies:
        python-pptx: Install with `pip install python-pptx`
    """

    def convert(self, path: Path, raw_content: str | bytes | None = None) -> str:
        """Convert a PowerPoint presentation to Markdown.

        Args:
            path: Path to the PowerPoint file.
            raw_content: Ignored for PowerPoint files (binary format).

        Returns:
            Markdown-formatted string with all slides.
        """
        _ = raw_content
        try:
            presentation_factory = importlib.import_module("pptx").Presentation
        except ModuleNotFoundError as e:
            msg = "Missing optional dependency `python-pptx`. Install with `pip install python-pptx`."
            raise ModuleNotFoundError(msg) from e

        start = time.time()

        prs = presentation_factory(str(path))
        parts = []

        for i, slide in enumerate(prs.slides, start=1):
            slide_parts = [f"# Slide {i}/{len(prs.slides)}\n"]

            # Extract text from shapes
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    # Check if it's a title (larger font)
                    if shape.has_text_frame:
                        text_frame = shape.text_frame
                        if text_frame.paragraphs:
                            first_para = text_frame.paragraphs[0]
                            if first_para.font.size and first_para.font.size.pt >= TITLE_FONT_SIZE_PT:
                                slide_parts.append(f"## {shape.text.strip()}\n")
                            else:
                                slide_parts.append(shape.text.strip())
                        else:
                            slide_parts.append(shape.text.strip())
                    else:
                        slide_parts.append(shape.text.strip())

            # Extract tables
            for shape in slide.shapes:
                if shape.has_table:
                    table = shape.table
                    slide_parts.append("\n### Table\n")
                    slide_parts.append(self._convert_table(table))

            parts.append("\n".join(slide_parts))

        duration = time.time() - start
        self._log_conversion(path, duration)

        return "\n\n---\n\n".join(parts)

    def supports_pagination(self) -> bool:
        """PowerPoint supports slide-by-slide reading.

        Returns:
            True
        """
        return True

    def convert_page(self, path: Path, page: int, raw_content: str | bytes | None = None) -> str:
        """Convert a single slide to Markdown.

        Args:
            path: Path to the PowerPoint file.
            page: Slide number (1-indexed).
            raw_content: Ignored for PowerPoint files.

        Returns:
            Markdown-formatted string for the requested slide.

        Raises:
            ValueError: If slide number is out of range.
        """
        _ = raw_content
        try:
            presentation_factory = importlib.import_module("pptx").Presentation
        except ModuleNotFoundError as e:
            msg = "Missing optional dependency `python-pptx`. Install with `pip install python-pptx`."
            raise ModuleNotFoundError(msg) from e

        start = time.time()

        prs = presentation_factory(str(path))
        total_slides = len(prs.slides)

        if page < 1 or page > total_slides:
            msg = f"Slide {page} out of range. Presentation has {total_slides} slides."
            raise ValueError(msg)

        slide = prs.slides[page - 1]
        slide_parts = [f"# Slide {page}/{total_slides}\n"]

        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                if shape.has_text_frame:
                    text_frame = shape.text_frame
                    if text_frame.paragraphs:
                        first_para = text_frame.paragraphs[0]
                        if first_para.font.size and first_para.font.size.pt >= TITLE_FONT_SIZE_PT:
                            slide_parts.append(f"## {shape.text.strip()}\n")
                        else:
                            slide_parts.append(shape.text.strip())
                    else:
                        slide_parts.append(shape.text.strip())
                else:
                    slide_parts.append(shape.text.strip())

        for shape in slide.shapes:
            if shape.has_table:
                table = shape.table
                slide_parts.append("\n### Table\n")
                slide_parts.append(self._convert_table(table))

        duration = time.time() - start
        self._log_conversion(path, duration, page=page)

        return "\n".join(slide_parts)

    def get_total_pages(self, path: Path) -> int | None:
        """Get total number of slides in the presentation.

        Args:
            path: Path to the PowerPoint file.

        Returns:
            Total number of slides.
        """
        try:
            presentation_factory = importlib.import_module("pptx").Presentation
        except ModuleNotFoundError as e:
            msg = "Missing optional dependency `python-pptx`. Install with `pip install python-pptx`."
            raise ModuleNotFoundError(msg) from e

        prs = presentation_factory(str(path))
        return len(prs.slides)

    def _convert_table(self, table: _SlideTable) -> str:
        """Convert a PowerPoint table to Markdown.

        Args:
            table: The table object from python-pptx.

        Returns:
            Markdown table string.
        """
        rows = []
        for row_idx in range(len(table.rows)):
            cells = [table.cell(row_idx, col_idx).text.strip() for col_idx in range(len(table.columns))]
            rows.append(cells)

        if not rows:
            return ""

        headers = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []

        return self._format_as_table(data_rows, headers)
