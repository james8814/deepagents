"""Performance tests for file format converters.

These tests verify that converters meet performance requirements:
- Small files (< 1MB): < 1 second
- Medium files (1-10MB): < 5 seconds
- Large files (> 10MB): < 10 seconds with pagination support
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deepagents.middleware.converters.csv import CSVConverter
from deepagents.middleware.converters.pdf import PDFConverter
from deepagents.middleware.converters.registry import get_default_registry
from deepagents.middleware.converters.text import TextConverter
from deepagents.middleware.converters.utils import detect_mime_type


class TestTextConverterPerformance:
    """Performance tests for TextConverter."""

    def test_small_file_performance(self):
        """Test text conversion of small file (< 1MB equivalent) completes in < 1s."""
        converter = TextConverter()

        # Create a file with ~100KB of text (approximately 25K lines)
        content = "Line of text content for testing performance.\n" * 2500

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            start = time.time()
            result = converter.convert(temp_path)
            duration = time.time() - start

            assert duration < 1.0, f"Small file conversion took {duration:.2f}s, expected < 1s"
            assert len(result) > 0
        finally:
            temp_path.unlink()

    def test_medium_file_performance(self):
        """Test text conversion of medium file (1-5MB equivalent) completes in < 2s."""
        converter = TextConverter()

        # Create a file with ~1MB of text
        content = "Line of text content for testing performance with more data.\n" * 15000

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            start = time.time()
            result = converter.convert(temp_path)
            duration = time.time() - start

            assert duration < 2.0, f"Medium file conversion took {duration:.2f}s, expected < 2s"
            assert len(result) > 0
        finally:
            temp_path.unlink()


class TestCSVConverterPerformance:
    """Performance tests for CSVConverter."""

    def test_small_csv_performance(self):
        """Test CSV conversion of small file (< 1000 rows) completes in < 1s."""
        converter = CSVConverter()

        # Create CSV with 1000 rows
        lines = ["Name,Age,City,Country,Occupation"]
        lines.extend(f"Person{i},{20 + i % 50},City{i % 100},Country{i % 50},Job{i % 20}" for i in range(1000))
        content = "\n".join(lines)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            start = time.time()
            result = converter.convert(temp_path)
            duration = time.time() - start

            assert duration < 1.0, f"Small CSV conversion took {duration:.2f}s, expected < 1s"
            assert "Person0" in result
            assert "Person999" in result
        finally:
            temp_path.unlink()

    def test_medium_csv_performance(self):
        """Test CSV conversion of medium file (5000-10000 rows) completes in < 3s."""
        converter = CSVConverter()

        # Create CSV with 5000 rows
        lines = ["Name,Age,City,Country,Occupation"]
        lines.extend(f"Person{i},{20 + i % 50},City{i % 100},Country{i % 50},Job{i % 20}" for i in range(5000))
        content = "\n".join(lines)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            start = time.time()
            result = converter.convert(temp_path)
            duration = time.time() - start

            assert duration < 3.0, f"Medium CSV conversion took {duration:.2f}s, expected < 3s"
            assert len(result) > 0
        finally:
            temp_path.unlink()


class TestPDFConverterPerformance:
    """Performance tests for PDFConverter."""

    @patch("deepagents.middleware.converters.pdf.pdfplumber")
    def test_small_pdf_performance(self, mock_pdfplumber):
        """Test PDF conversion of small file (< 10 pages) completes in < 2s."""
        # Mock a 5-page PDF
        mock_pages = []
        for i in range(5):
            mock_page = MagicMock()
            mock_page.extract_text.return_value = f"Page {i + 1} content with some text."
            mock_page.extract_tables.return_value = []
            mock_pages.append(mock_page)

        mock_pdf = MagicMock()
        mock_pdf.pages = mock_pages
        mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        converter = PDFConverter()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_path = Path(f.name)

        try:
            start = time.time()
            result = converter.convert(temp_path)
            duration = time.time() - start

            assert duration < 2.0, f"Small PDF conversion took {duration:.2f}s, expected < 2s"
            assert "Page 1" in result
        finally:
            temp_path.unlink()

    @patch("deepagents.middleware.converters.pdf.pdfplumber")
    def test_large_pdf_pagination_performance(self, mock_pdfplumber):
        """Test PDF pagination performance for large files.

        Reading single page should be significantly faster than reading all pages.
        """
        # Mock a 100-page PDF
        mock_pages = []
        for i in range(100):
            mock_page = MagicMock()
            mock_page.extract_text.return_value = f"Page {i + 1} with substantial content. " * 50
            mock_page.extract_tables.return_value = []
            mock_pages.append(mock_page)

        mock_pdf = MagicMock()
        mock_pdf.pages = mock_pages
        mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        converter = PDFConverter()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Time full conversion
            start_full = time.time()
            _ = converter.convert(temp_path)
            duration_full = time.time() - start_full

            # Time single page conversion
            start_page = time.time()
            result_page = converter.convert_page(temp_path, 50)
            duration_page = time.time() - start_page

            # Single page should be at least 10x faster
            assert duration_page < duration_full / 10, (
                f"Single page ({duration_page:.2f}s) should be much faster than full conversion ({duration_full:.2f}s)"
            )
            assert "Page 50" in result_page
        finally:
            temp_path.unlink()


class TestConverterRegistryPerformance:
    """Performance tests for converter registry operations."""

    def test_registry_lookup_performance(self):
        """Test that registry lookups are fast (< 1ms per lookup)."""
        registry = get_default_registry()
        mime_types = ["text/plain", "application/pdf", "text/csv", "image/png"]

        start = time.time()
        for _ in range(1000):  # 1000 lookups
            for mime_type in mime_types:
                _ = registry.get(mime_type)
        duration = time.time() - start

        avg_lookup_time = duration / (1000 * len(mime_types))
        assert avg_lookup_time < 0.001, f"Average lookup time {avg_lookup_time:.4f}s, expected < 1ms"


class TestMIMETypeDetectionPerformance:
    """Performance tests for MIME type detection."""

    def test_mime_detection_performance(self):
        """Test that MIME type detection is fast (< 10ms per file)."""
        test_paths = [
            "/path/to/document.pdf",
            "/path/to/spreadsheet.xlsx",
            "/path/to/presentation.pptx",
            "/path/to/document.docx",
            "/path/to/data.csv",
            "/path/to/script.py",
            "/path/to/image.png",
        ]

        start = time.time()
        for _ in range(100):  # 100 iterations
            for path in test_paths:
                _ = detect_mime_type(path)
        duration = time.time() - start

        avg_detection_time = duration / (100 * len(test_paths))
        assert avg_detection_time < 0.01, f"Average MIME detection time {avg_detection_time:.4f}s, expected < 10ms"


@pytest.mark.performance
class TestAsyncConversionPerformance:
    """Performance tests for async conversion operations."""

    @pytest.mark.asyncio
    @patch("deepagents.middleware.converters.pdf.pdfplumber")
    async def test_async_conversion_non_blocking(self, mock_pdfplumber):
        """Test that async conversion doesn't block the event loop.

        This test verifies that multiple conversions can run concurrently
        without significant slowdown.
        """
        # Mock a PDF that takes some time to convert
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Content"
        mock_page.extract_tables.return_value = []

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page] * 10
        mock_pdfplumber.open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdfplumber.open.return_value.__exit__ = MagicMock(return_value=False)

        converter = PDFConverter()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Simulate concurrent conversions
            async def convert_async():
                return await asyncio.to_thread(converter.convert, temp_path)

            start = time.time()
            # Run 3 conversions concurrently
            results = await asyncio.gather(
                convert_async(),
                convert_async(),
                convert_async(),
            )
            duration = time.time() - start

            # Concurrent conversions should not take 3x as long as sequential
            # Allow 2x for thread pool overhead
            assert duration < 2.0, f"Concurrent conversions took {duration:.2f}s, expected efficient parallelization"
            assert all("Content" in r for r in results)
        finally:
            await asyncio.to_thread(temp_path.unlink)
